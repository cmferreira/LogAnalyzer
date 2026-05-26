from __future__ import annotations
import csv
import json
import os
from typing import Optional

from app.core.models import LogEntry


class CsvExporter:
    def export(self, entries: list[LogEntry], output_path: str) -> None:
        if not entries:
            return
        fieldnames = list(entries[0].to_dict().keys())
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for e in entries:
                writer.writerow(e.to_dict())


class JsonExporter:
    def export(self, entries: list[LogEntry], output_path: str) -> None:
        data = [e.to_dict() for e in entries]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


class TxtExporter:
    def export(self, entries: list[LogEntry], output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            for e in entries:
                ts = e.timestamp.isoformat() if e.timestamp else ""
                f.write(f"{ts}\t{e.level}\t{e.source_file}\t{e.message}\n")


def get_exporter(fmt: str):
    mapping = {"csv": CsvExporter, "json": JsonExporter, "txt": TxtExporter}
    cls = mapping.get(fmt.lower())
    if cls is None:
        raise ValueError(f"Unknown export format: {fmt}")
    return cls()
