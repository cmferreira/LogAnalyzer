from __future__ import annotations
import os
import time
import threading
from typing import Callable


class TailMonitor:
    """Monitors a file for new lines (tail -f equivalent)."""

    def __init__(
        self,
        path: str,
        callback: Callable[[list[str]], None],
        interval_ms: int = 500,
    ) -> None:
        self._path = path
        self._callback = callback
        self._interval = interval_ms / 1000.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_pos = 0
        self._paused = False
        self._buffer: list[str] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        try:
            self._last_pos = os.path.getsize(self._path)
        except OSError:
            self._last_pos = 0

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        with self._lock:
            if self._buffer:
                lines = self._buffer[:]
                self._buffer.clear()
                self._callback(lines)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._buffer)

    def _run(self) -> None:
        from app.readers.encoding_detector import detect_encoding
        encoding = detect_encoding(self._path)

        while not self._stop_event.is_set():
            try:
                current_size = os.path.getsize(self._path)
                if current_size < self._last_pos:
                    # File was rotated/truncated
                    self._last_pos = 0

                if current_size > self._last_pos:
                    with open(self._path, "rb") as f:
                        f.seek(self._last_pos)
                        raw = f.read(current_size - self._last_pos)
                    self._last_pos = current_size

                    text = raw.decode(encoding, errors="replace")
                    lines = [l.rstrip("\r\n") for l in text.splitlines() if l.strip()]

                    if lines:
                        if self._paused:
                            with self._lock:
                                self._buffer.extend(lines)
                        else:
                            self._callback(lines)

            except OSError:
                pass

            self._stop_event.wait(timeout=self._interval)
