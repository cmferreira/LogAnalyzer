from __future__ import annotations
import os
from typing import Optional

from app.core.interfaces import IParser
from app.parsers.generic_parser import GenericParser
from app.parsers.json_parser import JsonParser
from app.parsers.syslog_parser import SyslogParser
from app.parsers.apache_parser import (
    ApacheAccessParser, ApacheErrorParser, NginxAccessParser, NginxErrorParser
)
from app.parsers.java_parser import JavaParser
from app.parsers.docker_parser import DockerParser, K8sParser
from app.parsers.csv_parser import CsvParser
from app.parsers.xml_parser import XmlParser
from app.parsers.windows_event_parser import EvtxParser

# Ordered by specificity (most specific first)
_ALL_PARSERS: list[IParser] = [
    EvtxParser(),
    JsonParser(),
    CsvParser(),
    XmlParser(),
    SyslogParser(),
    ApacheAccessParser(),
    ApacheErrorParser(),
    NginxAccessParser(),
    NginxErrorParser(),
    JavaParser(),
    DockerParser(),
    K8sParser(),
    GenericParser(),
]

_EXT_HINTS: dict[str, list[str]] = {
    ".evtx": ["evtx"],
    ".json": ["json"],
    ".jsonl": ["json"],
    ".ndjson": ["json"],
    ".csv": ["csv"],
    ".tsv": ["csv"],
    ".xml": ["xml"],
}

# All extensions accepted by the application (used for UI validation)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".log", ".txt", ".out", ".err", ".syslog",
    ".json", ".jsonl", ".ndjson",
    ".csv", ".tsv",
    ".xml",
    ".evtx",
})

# Extensions that are known binary/unsupported formats with a helpful hint
_BINARY_HINTS: dict[str, str] = {
    ".exe": "Executable binary — not a log file.",
    ".dll": "DLL binary — not a log file.",
    ".zip": "Compressed archive. Extract the log files first.",
    ".gz":  "Compressed file. Decompress first (e.g. with 7-Zip).",
    ".tar": "Archive file. Extract the log files first.",
    ".png": "Image file — not a log file.",
    ".jpg": "Image file — not a log file.",
    ".pdf": "PDF document — not a log file.",
    ".docx": "Word document — not a log file.",
    ".xlsx": "Excel spreadsheet — not a log file.",
}


class FileValidationError(Exception):
    """Raised when a file cannot be opened by LogAnalyzer."""


class AutoDetector:
    def validate(self, path: str) -> None:
        """Raise FileValidationError with a clear message if the file cannot be parsed."""
        import os

        if not os.path.exists(path):
            raise FileValidationError(f"File not found:\n{path}")

        if not os.path.isfile(path):
            raise FileValidationError(f"Not a file (directory or special path):\n{path}")

        if os.path.getsize(path) == 0:
            raise FileValidationError(f"File is empty:\n{os.path.basename(path)}")

        try:
            with open(path, "rb"):
                pass
        except PermissionError:
            raise FileValidationError(
                f"Permission denied — cannot read file:\n{os.path.basename(path)}"
            )
        except OSError as e:
            raise FileValidationError(
                f"Cannot open file ({e.strerror}):\n{os.path.basename(path)}"
            )

        ext = os.path.splitext(path)[1].lower()

        if ext in _BINARY_HINTS:
            raise FileValidationError(
                f"Unsupported file type '{ext}'.\n{_BINARY_HINTS[ext]}"
            )

        if ext and ext not in SUPPORTED_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported extension '{ext}'.\n\n"
                f"Supported extensions:\n"
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}\n\n"
                "You can still try opening it via 'All Files (*.*)' — "
                "LogAnalyzer will attempt generic parsing."
            )

    def detect(self, path: str, sample_lines: list[str] | None = None) -> IParser:
        ext = os.path.splitext(path)[1].lower()

        # Binary magic bytes check for EVTX
        try:
            with open(path, "rb") as f:
                header = f.read(8)
            if header == b"ElfFile\x00":
                return EvtxParser()
        except OSError:
            pass

        if sample_lines is None:
            sample_lines = self._read_sample(path)

        # Extension shortcut
        if ext in _EXT_HINTS:
            for parser_name in _EXT_HINTS[ext]:
                for p in _ALL_PARSERS:
                    if p.name == parser_name:
                        score = p.probe(sample_lines)
                        if score >= 0.5:
                            return p

        # Score all parsers
        best_parser: IParser = GenericParser()
        best_score = 0.0

        for parser in _ALL_PARSERS:
            if isinstance(parser, (GenericParser, EvtxParser)):
                continue
            try:
                score = parser.probe(sample_lines)
                if score > best_score:
                    best_score = score
                    best_parser = parser
            except Exception:
                continue

        if best_score < 0.3:
            return GenericParser()

        return best_parser

    @staticmethod
    def _read_sample(path: str, n_lines: int = 50) -> list[str]:
        try:
            with open(path, "rb") as f:
                raw = f.read(32 * 1024)
            try:
                import chardet
                enc = chardet.detect(raw).get("encoding") or "utf-8"
            except Exception:
                enc = "utf-8"
            text = raw.decode(enc, errors="replace")
            return text.splitlines()[:n_lines]
        except OSError:
            return []

    @staticmethod
    def all_parsers() -> list[IParser]:
        return _ALL_PARSERS
