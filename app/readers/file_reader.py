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
                    yield from self._read_mmap_with_fallback(
                        f, file_size, encoding, progress_cb
                    )
                else:
                    yield from self._read_normal(f, file_size, encoding, progress_cb)
        except PermissionError as e:
            raise PermissionError(
                f"Sem permissão para ler o ficheiro: {os.path.basename(path)}"
            ) from e
        except OSError as e:
            raise OSError(
                _friendly_oserror(e, os.path.basename(path))
            ) from e

    def _read_mmap_with_fallback(
        self,
        f,
        file_size: int,
        encoding: str,
        progress_cb: Callable[[float], None] | None,
    ) -> Iterator[list[str]]:
        """Try mmap; if it fails (e.g. file locked, special flags), fall back to normal read."""
        try:
            yield from self._read_mmap(f, file_size, encoding, progress_cb)
        except (OSError, mmap.error):
            # Reset file position and fall back to line-by-line
            try:
                f.seek(0)
            except OSError:
                return
            yield from self._read_normal(f, file_size, encoding, progress_cb)

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


def _friendly_oserror(e: OSError, filename: str) -> str:
    """Convert a raw OSError into a user-friendly message."""
    errno_messages = {
        2:  f"Ficheiro não encontrado: {filename}",
        5:  f"Acesso negado (Access Denied): {filename}",
        13: f"Sem permissão para ler: {filename}",
        22: (
            f"Não foi possível ler o ficheiro: {filename}\n\n"
            "Possíveis causas:\n"
            "  • O ficheiro está a ser usado por outro processo\n"
            "  • O ficheiro está bloqueado (locked)\n"
            "  • Path com caracteres inválidos\n"
            "  • Ficheiro de sistema ou pipe especial\n\n"
            "Sugestão: feche o processo que está a usar o ficheiro e tente novamente."
        ),
        32: f"O ficheiro está aberto por outro processo: {filename}",
        33: f"O ficheiro está bloqueado: {filename}",
    }
    code = e.errno or 0
    return errno_messages.get(code, f"Erro ao ler ficheiro ({e.strerror}): {filename}")
