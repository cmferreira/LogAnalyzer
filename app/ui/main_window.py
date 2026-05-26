from __future__ import annotations
import os
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QToolBar, QFileDialog,
    QMessageBox, QProgressBar, QLabel, QTabWidget,
    QApplication, QMenu, QMenuBar, QDialog,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QKeySequence, QAction, QIcon

from app.core.models import LogEntry, LogFile, FilterState
from app.core.constants import APP_NAME, APP_VERSION, LEVELS_ORDERED
from app.search.indexer import LogIndex
from app.search.search_engine import SearchEngine
from app.correlation.correlator import Correlator
from app.correlation.timeline import UnifiedTimeline
from app.config.config_manager import ConfigManager
from app.parsers.auto_detector import AutoDetector, FileValidationError
from app.ui.log_table import LogTableModel, LogTableView
from app.ui.search_bar import SearchBar
from app.ui.filter_panel import FilterPanel
from app.ui.detail_panel import DetailPanel
from app.ui.file_panel import FilePanel
from app.ui.correlation_view import CorrelationView
from app.ui.workers import LoaderWorker, LiveMonitorWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._cfg = ConfigManager.instance()
        self._dark = self._cfg.theme == "dark"
        self._index = LogIndex()
        self._engine = SearchEngine(self._index)
        self._correlator = Correlator(self._index)
        self._timeline = UnifiedTimeline(self._index)
        self._log_files: dict[str, LogFile] = {}
        self._active_workers: list[LoaderWorker] = []
        self._live_workers: dict[str, LiveMonitorWorker] = {}
        self._current_filter = FilterState()
        self._auto_scroll = self._cfg.get("auto_scroll", True)
        self._model: Optional[LogTableModel] = None

        self._build_ui()
        self._restore_geometry()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")

    def _build_ui(self) -> None:
        self._build_menu()
        self._build_toolbar()

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # Search bar at top
        self._search_bar = SearchBar()
        self._search_bar.search_changed.connect(self._on_search_changed)
        self._search_bar.cleared.connect(self._on_search_cleared)
        root_layout.addWidget(self._search_bar)

        # Main horizontal splitter
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(self._main_splitter)

        # Left panel: files + filters in vertical splitter
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        self._file_panel = FilePanel()
        self._file_panel.file_close_requested.connect(self._close_file)
        self._file_panel.file_live_requested.connect(self._start_live)
        left_splitter.addWidget(self._file_panel)
        self._filter_panel = FilterPanel()
        self._filter_panel.filter_changed.connect(self._on_filter_changed)
        left_splitter.addWidget(self._filter_panel)
        left_splitter.setSizes([200, 400])
        self._main_splitter.addWidget(left_splitter)

        # Center + right: vertical splitter (table + detail)
        center_splitter = QSplitter(Qt.Orientation.Vertical)

        # Tab widget for log table / correlation view
        self._view_tabs = QTabWidget()
        self._view_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # Log table tab
        self._index = LogIndex()
        self._engine = SearchEngine(self._index)
        self._correlator = Correlator(self._index)
        self._timeline = UnifiedTimeline(self._index)
        self._model = LogTableModel(self._index, dark_mode=self._dark)
        self._table_view = LogTableView(self._model)
        self._table_view.entry_selected.connect(self._on_entry_selected)
        self._view_tabs.addTab(self._table_view, "Log View")

        # Correlation tab
        self._corr_view = CorrelationView()
        self._corr_view.entry_selected.connect(self._on_entry_selected)
        self._view_tabs.addTab(self._corr_view, "Correlation")

        center_splitter.addWidget(self._view_tabs)

        # Detail panel at bottom — starts collapsed, expands on first entry click
        self._detail = DetailPanel()
        self._detail.correlate_requested.connect(self._on_correlate_id)
        center_splitter.addWidget(self._detail)
        center_splitter.setSizes([900, 0])
        self._center_splitter = center_splitter

        self._main_splitter.addWidget(center_splitter)
        self._main_splitter.setSizes([240, 1160])

        # Restore splitter
        saved_sizes = self._cfg.get("splitter_sizes", [])
        if saved_sizes:
            try:
                self._main_splitter.setSizes(saved_sizes)
            except Exception:
                pass

        self._build_status_bar()

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("&File")
        open_act = QAction("&Open File(s)…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_files_dialog)
        file_menu.addAction(open_act)

        self._recent_menu = file_menu.addMenu("Recent Files")
        self._rebuild_recent_menu()

        file_menu.addSeparator()
        export_act = QAction("&Export…", self)
        export_act.setShortcut("Ctrl+E")
        export_act.triggered.connect(self._export_dialog)
        file_menu.addAction(export_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # View
        view_menu = mb.addMenu("&View")
        theme_act = QAction("Toggle &Theme", self)
        theme_act.setShortcut("Ctrl+T")
        theme_act.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_act)

        raw_act = QAction("Show Raw Column", self)
        raw_act.setCheckable(True)
        raw_act.setChecked(self._cfg.get("show_raw_column", False))
        raw_act.toggled.connect(lambda v: self._table_view.toggle_raw_column(v))
        view_menu.addAction(raw_act)

        view_menu.addSeparator()
        scroll_act = QAction("Auto-scroll", self)
        scroll_act.setCheckable(True)
        scroll_act.setChecked(self._auto_scroll)
        scroll_act.toggled.connect(self._toggle_auto_scroll)
        view_menu.addAction(scroll_act)

        # Correlation
        corr_menu = mb.addMenu("&Correlate")
        run_corr = QAction("Run Correlation", self)
        run_corr.setShortcut("Ctrl+Shift+C")
        run_corr.triggered.connect(self._run_correlation)
        corr_menu.addAction(run_corr)

        # Help
        help_menu = mb.addMenu("&Help")
        about_act = QAction("&About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        open_act = QAction("Open", self)
        open_act.setToolTip("Open log file(s) (Ctrl+O)")
        open_act.triggered.connect(self._open_files_dialog)
        tb.addAction(open_act)

        tb.addSeparator()

        self._live_act = QAction("▶ Live", self)
        self._live_act.setToolTip("Start live monitoring of active file")
        self._live_act.triggered.connect(self._start_live_current)
        tb.addAction(self._live_act)

        self._pause_act = QAction("⏸ Pause", self)
        self._pause_act.setToolTip("Pause live updates")
        self._pause_act.triggered.connect(self._pause_live)
        self._pause_act.setEnabled(False)
        tb.addAction(self._pause_act)

        self._resume_act = QAction("▶ Resume", self)
        self._resume_act.setToolTip("Resume live updates")
        self._resume_act.triggered.connect(self._resume_live)
        self._resume_act.setEnabled(False)
        tb.addAction(self._resume_act)

        tb.addSeparator()

        corr_act = QAction("Correlate", self)
        corr_act.setToolTip("Run correlation engine (Ctrl+Shift+C)")
        corr_act.triggered.connect(self._run_correlation)
        tb.addAction(corr_act)

        tb.addSeparator()

        export_act = QAction("Export", self)
        export_act.setToolTip("Export filtered results")
        export_act.triggered.connect(self._export_dialog)
        tb.addAction(export_act)

        tb.addSeparator()

        clear_act = QAction("Clear All", self)
        clear_act.setToolTip("Clear all loaded logs")
        clear_act.triggered.connect(self._clear_all)
        tb.addAction(clear_act)

    def _build_status_bar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, 1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setVisible(False)
        sb.addPermanentWidget(self._progress_bar)

        self._count_label = QLabel("0 entries")
        sb.addPermanentWidget(self._count_label)

        self._live_label = QLabel("")
        self._live_label.setStyleSheet("color: #4CAF50;")
        sb.addPermanentWidget(self._live_label)

    # ─── File operations ────────────────────────────────────────────────────

    def _open_files_dialog(self) -> None:
        last_folder = self._cfg.get("last_folder", "")
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Log Files",
            last_folder,
            "Log Files (*.log *.txt *.out *.err *.syslog *.json *.jsonl *.ndjson *.csv *.tsv *.xml *.evtx);;"
            "All Files (*.*)",
        )
        if paths:
            self._cfg.set("last_folder", os.path.dirname(paths[0]))
            for path in paths:
                self._load_file(path)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        errors: list[str] = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                try:
                    AutoDetector().validate(path)
                    self._load_file(path)
                except FileValidationError as e:
                    errors.append(str(e))
        if errors:
            QMessageBox.warning(self, "Cannot Open File(s)", "\n\n---\n\n".join(errors))

    def _load_file(self, path: str) -> None:
        if path in self._log_files:
            self._status(f"Already loaded: {os.path.basename(path)}")
            return

        # Validate before committing any state changes
        try:
            AutoDetector().validate(path)
        except FileValidationError as e:
            self._status(f"Cannot open: {os.path.basename(path)}")
            QMessageBox.warning(
                self,
                "Cannot Open File",
                str(e),
            )
            return

        log_file = LogFile(path=path)
        self._log_files[path] = log_file
        self._file_panel.add_file(log_file)
        self._cfg.add_recent_file(path)
        self._rebuild_recent_menu()

        worker = LoaderWorker(path, self._index, self)
        worker.progress.connect(self._on_load_progress)
        worker.progress.connect(lambda p, _p=path: self._file_panel.set_loading(_p, int(p * 100)))
        worker.chunk_ready.connect(self._on_chunk_ready)
        worker.status.connect(self._status)
        worker.finished.connect(self._on_load_finished)
        worker.error.connect(self._on_load_error)
        worker.error.connect(lambda _msg, _p=path: self._file_panel.clear_loading(_p))
        self._active_workers.append(worker)
        self._progress_bar.setVisible(True)
        worker.start()

    def _close_file(self, path: str) -> None:
        self._log_files.pop(path, None)
        self._file_panel.remove_file(path)
        # Full reload needed since index is shared
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._index.clear()
        self._model.invalidate_cache()
        paths = list(self._log_files.keys())
        self._log_files.clear()
        self._file_panel._files.clear()
        self._file_panel._refresh_tree()
        for path in paths:
            self._load_file(path)

    def _clear_all(self) -> None:
        for w in self._active_workers:
            w.cancel()
        self._active_workers.clear()
        for w in self._live_workers.values():
            w.stop_monitoring()
        self._live_workers.clear()
        self._index.clear()
        self._log_files.clear()
        self._file_panel._files.clear()
        self._file_panel._refresh_tree()
        self._model.refresh()
        self._status("Cleared.")
        self._count_label.setText("0 entries")

    # ─── Load events ────────────────────────────────────────────────────────

    def _on_load_progress(self, pct: float) -> None:
        self._progress_bar.setValue(int(pct * 100))

    def _on_chunk_ready(self, entries: list) -> None:
        self._model.invalidate_cache()
        self._model.refresh()
        if self._auto_scroll:
            QTimer.singleShot(50, self._table_view.scroll_to_bottom)

    def _on_load_finished(self, log_file: LogFile) -> None:
        self._file_panel.clear_loading(log_file.path)
        self._log_files[log_file.path] = log_file
        self._file_panel.update_file(log_file)
        self._model.refresh()
        self._auto_hide_empty_columns()
        total = self._index.total_count()
        self._count_label.setText(f"{total:,} entries")
        self._progress_bar.setVisible(False)
        self._status(f"Loaded: {os.path.basename(log_file.path)} — {log_file.entry_count:,} entries")

    def _auto_hide_empty_columns(self) -> None:
        """Hide optional columns (Host, PID, TID, Corr ID) when they have no data."""
        checks = [(3, "hostname"), (4, "pid"), (5, "tid"), (6, "correlation_id")]
        for col_idx, field in checks:
            has_data = self._index.count_non_empty(field) > 0
            self._table_view.setColumnHidden(col_idx, not has_data)

    def _on_load_error(self, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._status(f"Error: {msg}")
        QMessageBox.warning(self, "Load Error", msg)

    # ─── Live monitoring ─────────────────────────────────────────────────────

    def _start_live_current(self) -> None:
        if not self._log_files:
            QMessageBox.information(self, "No File", "Open a file first.")
            return
        path = list(self._log_files.keys())[-1]
        self._start_live(path)

    def _start_live(self, path: str) -> None:
        if path in self._live_workers:
            return
        detector = AutoDetector()
        parser = detector.detect(path)
        worker = LiveMonitorWorker(path, parser, self)
        worker.new_entries.connect(self._on_live_entries)
        worker.error.connect(lambda e: self._status(f"Live error: {e}"))
        self._live_workers[path] = worker
        worker.start()

        if path in self._log_files:
            self._log_files[path].is_live = True
            self._file_panel.update_file(self._log_files[path])

        self._live_label.setText("● LIVE")
        self._pause_act.setEnabled(True)
        self._status(f"Live monitoring: {os.path.basename(path)}")

    def _pause_live(self) -> None:
        for w in self._live_workers.values():
            w.pause()
        self._pause_act.setEnabled(False)
        self._resume_act.setEnabled(True)
        self._live_label.setText("⏸ PAUSED")

    def _resume_live(self) -> None:
        for w in self._live_workers.values():
            w.resume()
        self._pause_act.setEnabled(True)
        self._resume_act.setEnabled(False)
        self._live_label.setText("● LIVE")

    def _on_live_entries(self, entries: list) -> None:
        self._index.insert_batch(entries)
        self._model.invalidate_cache()
        self._model.refresh()
        if self._auto_scroll:
            QTimer.singleShot(50, self._table_view.scroll_to_bottom)
        total = self._index.total_count()
        self._count_label.setText(f"{total:,} entries")

    # ─── Search / filter ────────────────────────────────────────────────────

    def _on_search_changed(self, text: str, regex: bool, case_sensitive: bool) -> None:
        self._current_filter.search_text = text
        self._current_filter.regex_mode = regex
        self._current_filter.case_sensitive = case_sensitive
        if text:
            self._cfg.add_search_history(text)
        self._apply_filter()

    def _on_search_cleared(self) -> None:
        self._current_filter.search_text = ""
        self._apply_filter()

    def _on_filter_changed(self, f: FilterState) -> None:
        # Merge search state
        f.search_text = self._current_filter.search_text
        f.regex_mode = self._current_filter.regex_mode
        f.case_sensitive = self._current_filter.case_sensitive
        self._current_filter = f
        self._apply_filter()

    def _apply_filter(self) -> None:
        self._model.set_filter(
            None if self._current_filter.is_empty() else self._current_filter
        )
        total = self._model.rowCount()
        self._count_label.setText(f"{total:,} entries")
        self._search_bar.set_result_count(total, self._index.total_count())

    # ─── Entry selection ────────────────────────────────────────────────────

    def _on_entry_selected(self, entry: LogEntry) -> None:
        self._detail.show_entry(entry)
        sizes = self._center_splitter.sizes()
        if sizes[1] < 80:
            total = sizes[0] + sizes[1]
            self._center_splitter.setSizes([total - 220, 220])

    def _on_correlate_id(self, corr_id: str) -> None:
        entries = self._index.get_entries_by_correlation_id(corr_id)
        if entries:
            self._view_tabs.setCurrentIndex(1)
            self._corr_view.show_entries(entries)
            self._status(f"Showing {len(entries)} correlated events for ID: {corr_id[:20]}")

    # ─── Correlation ─────────────────────────────────────────────────────────

    def _run_correlation(self) -> None:
        self._status("Running correlation…")
        groups = self._correlator.get_all_groups()
        self._corr_view.load_groups(groups)

        for g in groups:
            entries = self._index.get_entries_by_correlation_id(g.value) if g.criteria == "correlation_id" else []
            self._corr_view.register_group_entries(g.group_id, entries)

        self._view_tabs.setCurrentIndex(1)
        self._status(f"Correlation complete: {len(groups)} groups found.")

    # ─── Export ──────────────────────────────────────────────────────────────

    def _export_dialog(self) -> None:
        from app.export.exporters import get_exporter

        path, sel_filter = QFileDialog.getSaveFileName(
            self, "Export Logs", "",
            "CSV (*.csv);;JSON (*.json);;Text (*.txt)"
        )
        if not path:
            return

        fmt = "csv"
        if path.endswith(".json"):
            fmt = "json"
        elif path.endswith(".txt"):
            fmt = "txt"

        total = self._engine.count(self._current_filter)
        if total == 0:
            QMessageBox.information(self, "Empty", "No entries to export.")
            return

        entries = self._engine.get_page(0, min(total, 1_000_000), self._current_filter)

        try:
            exporter = get_exporter(fmt)
            exporter.export(entries, path)
            self._status(f"Exported {len(entries):,} entries to {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    # ─── Theme ───────────────────────────────────────────────────────────────

    def _toggle_theme(self) -> None:
        self._dark = not self._dark
        self._cfg.theme = "dark" if self._dark else "light"
        self._cfg.save()
        from app.ui.theme_manager import apply_theme
        apply_theme(QApplication.instance(), self._cfg.theme)
        self._model.set_dark_mode(self._dark)

    def _toggle_auto_scroll(self, enabled: bool) -> None:
        self._auto_scroll = enabled
        self._cfg.set("auto_scroll", enabled)

    # ─── Recent files ────────────────────────────────────────────────────────

    def _rebuild_recent_menu(self) -> None:
        self._recent_menu.clear()
        recents = self._cfg.get("recent_files", [])
        if not recents:
            self._recent_menu.addAction("(empty)")
            return
        for path in recents:
            act = QAction(os.path.basename(path), self)
            act.setToolTip(path)
            act.triggered.connect(lambda checked=False, p=path: self._load_file(p))
            self._recent_menu.addAction(act)

    # ─── Status / geometry ───────────────────────────────────────────────────

    def _status(self, text: str) -> None:
        self._status_label.setText(text)

    def _restore_geometry(self) -> None:
        win = self._cfg.get("window", {})
        x = win.get("x", 100)
        y = win.get("y", 100)
        w = win.get("width", 1400)
        h = win.get("height", 900)
        self.setGeometry(x, y, w, h)
        if win.get("maximized", False):
            self.showMaximized()

    def closeEvent(self, event) -> None:
        for w in self._active_workers:
            w.cancel()
        for w in self._live_workers.values():
            w.stop_monitoring()

        geo = self.geometry()
        self._cfg.set("window", {
            "x": geo.x(), "y": geo.y(),
            "width": geo.width(), "height": geo.height(),
            "maximized": self.isMaximized(),
        })
        self._cfg.set("splitter_sizes", self._main_splitter.sizes())
        self._cfg.save()
        self._index.close()
        event.accept()

    def _show_about(self) -> None:
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME} {APP_VERSION}</b><br><br>"
            "Portable log analysis, search, visualization, and correlation tool.<br><br>"
            "Supports: JSON, Syslog, Apache, Nginx, Java, Docker, K8s, CSV, XML, EVTX<br><br>"
            "No installation required."
        )
