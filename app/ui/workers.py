from __future__ import annotations
import os
import threading
from typing import Optional

from PySide6.QtCore import QThread, Signal, QObject

from app.core.models import LogEntry, LogFile
from app.parsers.auto_detector import AutoDetector
from app.parsers.windows_event_parser import EvtxParser
from app.parsers.base_parser import BaseParser
from app.readers.file_reader import FileReader
from app.readers.encoding_detector import detect_encoding
from app.search.indexer import LogIndex


class LoaderWorker(QThread):
    """Loads and parses a log file in the background."""

    progress = Signal(float)           # 0.0–1.0
    chunk_ready = Signal(list)         # list[LogEntry]
    status = Signal(str)               # status text
    finished = Signal(object)          # LogFile
    error = Signal(str)

    def __init__(self, path: str, index: LogIndex, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._path = path
        self._index = index
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        path = self._path
        log_file = LogFile(path=path)

        try:
            if not os.path.exists(path):
                self.error.emit(f"File not found: {path}")
                return

            file_size = os.path.getsize(path)
            log_file.size_bytes = file_size

            self.status.emit(f"Detecting format: {os.path.basename(path)}")
            detector = AutoDetector()
            parser = detector.detect(path)
            log_file.parser_name = parser.name
            log_file.format_name = parser.name

            # EVTX: special binary parser
            if isinstance(parser, EvtxParser):
                self.status.emit("Parsing Windows Event Log…")
                self._index.begin_bulk_load()
                try:
                    entries = parser.parse_file(path, path)
                    log_file.encoding = "binary"
                    if entries:
                        self._index.insert_batch(entries)
                        self.chunk_ready.emit(entries)
                        log_file.entry_count = len(entries)
                finally:
                    self._index.end_bulk_load()
                self.progress.emit(1.0)
                log_file.load_complete = True
                self.finished.emit(log_file)
                return

            encoding = detect_encoding(path)
            log_file.encoding = encoding

            reader = FileReader()
            total_entries = 0

            self.status.emit(f"Parsing {os.path.basename(path)} ({parser.name})")

            self._index.begin_bulk_load()
            try:
                for chunk_lines in reader.read_chunks(
                    path,
                    encoding,
                    progress_cb=lambda p: self.progress.emit(p),
                ):
                    if self._cancel.is_set():
                        self.status.emit("Cancelled.")
                        return

                    entries = parser.parse_lines(chunk_lines, path)
                    if entries:
                        self._index.insert_batch(entries)
                        self.chunk_ready.emit(entries)
                        total_entries += len(entries)
                        log_file.entry_count = total_entries
            finally:
                self._index.end_bulk_load()

            log_file.load_complete = True
            self.progress.emit(1.0)
            self.status.emit(f"Loaded {total_entries:,} entries from {os.path.basename(path)}")
            self.finished.emit(log_file)

        except PermissionError as e:
            self.error.emit(f"Permission denied: {path}")
        except OSError as e:
            self.error.emit(f"File error: {e}")
        except Exception as e:
            self.error.emit(f"Parse error ({os.path.basename(path)}): {e}")


class LiveMonitorWorker(QThread):
    """Tail-follows a file and emits new entries."""

    new_entries = Signal(list)   # list[LogEntry]
    error = Signal(str)
    pending_count_changed = Signal(int)

    def __init__(
        self,
        path: str,
        parser: BaseParser,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._parser = parser
        self._monitor = None
        self._paused = False

    def pause(self) -> None:
        if self._monitor:
            self._monitor.pause()

    def resume(self) -> None:
        if self._monitor:
            self._monitor.resume()

    def run(self) -> None:
        from app.monitoring.file_monitor import TailMonitor

        def on_lines(lines: list[str]) -> None:
            try:
                entries = self._parser.parse_lines(lines, self._path)
                if entries:
                    self.new_entries.emit(entries)
            except Exception as e:
                self.error.emit(str(e))

        self._monitor = TailMonitor(
            self._path, on_lines,
            interval_ms=500,
        )
        self._monitor.start()
        # Block thread until quit() is called
        self.exec()
        self._monitor.stop()

    def stop_monitoring(self) -> None:
        if self._monitor:
            self._monitor.stop()
        self.quit()
