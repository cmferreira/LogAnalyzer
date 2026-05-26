from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.models import LogEntry, LogFile


class IParser(ABC):
    name: str = "base"
    supported_extensions: list[str] = []

    @abstractmethod
    def probe(self, sample_lines: list[str]) -> float:
        """Return confidence 0.0–1.0 that this parser handles the sample."""

    @abstractmethod
    def parse_lines(self, lines: list[str], source_file: str) -> list["LogEntry"]:
        """Parse a batch of raw lines into LogEntry objects."""


class IReader(ABC):
    @abstractmethod
    def read_chunks(self, path: str, encoding: str) -> Iterator[list[str]]:
        """Yield chunks of raw text lines."""


class IExporter(ABC):
    @abstractmethod
    def export(self, entries: list["LogEntry"], output_path: str) -> None:
        """Write entries to output_path."""


class IMonitor(ABC):
    @abstractmethod
    def start(self, path: str) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...
