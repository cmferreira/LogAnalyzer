from __future__ import annotations
import mmap
import os
import threading
from typing import Iterator, Callable

from app.core.constants import CHUNK_SIZE, LARGE_FILE_THRESHOLD
from app.readers.encoding_detector import detect_encoding


class FileReader:
    def __init__(self, chunk_size: int = CHUNK_SIZE) -> None:
        self._chunk_size = chunk_size
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def reset(self) -> None:
        self._cancel_event.clear()

    def read_chunks(
        self,
        path: str,
        encoding: str | None = None,
        progress_cb: Callable[[float], None] | None = None,
    ) -> Iterator[list[str]]:
        if encoding is None:
            encoding = detect_encoding(path)

        file_size = os.path.getsize(path)
        use_mmap = file_size >= LARGE_FILE_THRESHOLD

        try:
            with open(path, "rb") as f:
                if use_mmap and file_size > 0:
                    yield from self._read_mmap(f, file_size, encoding, progress_cb)
                else:
                    yield from self._read_normal(f, file_size, encoding, progress_cb)
        except PermissionError as e:
            raise PermissionError(f"Cannot open file (permission denied): {path}") from e
        except OSError as e:
            raise OSError(f"Cannot open file: {path} — {e}") from e

    def _read_mmap(
        self,
        f,
        file_size: int,
        encoding: str,
        progress_cb: Callable[[float], None] | None,
    ) -> Iterator[list[str]]:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            bytes_read = 0
            chunk: list[str] = []
            pos = 0

            while pos < file_size:
                if self._cancel_event.is_set():
                    return

                newline_pos = mm.find(b"\n", pos)
                if newline_pos == -1:
                    raw = mm[pos:]
                    pos = file_size
                else:
                    raw = mm[pos:newline_pos]
                    pos = newline_pos + 1

                bytes_read += len(raw) + 1
                line = raw.rstrip(b"\r").decode(encoding, errors="replace")
                chunk.append(line)

                if len(chunk) >= self._chunk_size:
                    if progress_cb:
                        progress_cb(bytes_read / file_size)
                    yield chunk
                    chunk = []

            if chunk:
                if progress_cb:
                    progress_cb(1.0)
                yield chunk

    def _read_normal(
        self,
        f,
        file_size: int,
        encoding: str,
        progress_cb: Callable[[float], None] | None,
    ) -> Iterator[list[str]]:
        bytes_read = 0
        chunk: list[str] = []

        for raw_line in f:
            if self._cancel_event.is_set():
                return
            bytes_read += len(raw_line)
            line = raw_line.decode(encoding, errors="replace").rstrip("\r\n")
            chunk.append(line)

            if len(chunk) >= self._chunk_size:
                if progress_cb and file_size > 0:
                    progress_cb(bytes_read / file_size)
                yield chunk
                chunk = []

        if chunk:
            if progress_cb:
                progress_cb(1.0)
            yield chunk
