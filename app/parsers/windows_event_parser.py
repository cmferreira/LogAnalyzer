from __future__ import annotations
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp


class EvtxParser(BaseParser):
    name = "evtx"
    supported_extensions = [".evtx"]

    def probe(self, sample_lines: list[str]) -> float:
        return 0.0  # Binary file — detected by magic bytes in auto_detector

    def probe_binary(self, header: bytes) -> float:
        if header[:8] == b"ElfFile\x00":
            return 0.99
        return 0.0

    def parse_file(self, path: str, source_file: str) -> list[LogEntry]:
        try:
            from Evtx.Evtx import Evtx
            from Evtx.Views import evtx_file_xml_view
        except ImportError:
            return [LogEntry(
                id=self._next_id(),
                source_file=source_file,
                message="python-evtx not installed. Install with: pip install python-evtx",
                level="ERROR",
            )]

        entries: list[LogEntry] = []
        _level_map = {"1": "CRITICAL", "2": "ERROR", "3": "WARN", "4": "INFO", "5": "DEBUG"}

        try:
            with Evtx(path) as log:
                for xml_str, record in evtx_file_xml_view(log.get_file_header()):
                    try:
                        entry = self._parse_xml_str(xml_str, source_file, _level_map)
                        if entry:
                            entry.id = self._next_id()
                            entries.append(entry)
                    except Exception:
                        continue
        except Exception as e:
            entries.append(LogEntry(
                id=self._next_id(),
                source_file=source_file,
                message=f"Error reading EVTX: {e}",
                level="ERROR",
            ))

        return entries

    def _parse_xml_str(self, xml_str: str, source_file: str, level_map: dict) -> Optional[LogEntry]:
        try:
            from lxml import etree
        except ImportError:
            import xml.etree.ElementTree as etree  # type: ignore

        try:
            root = etree.fromstring(xml_str.encode("utf-8"))
        except Exception:
            return None

        ns = "http://schemas.microsoft.com/win/2004/08/events/event"
        entry = LogEntry(source_file=source_file)

        sys_el = root.find(f"{{{ns}}}System")
        if sys_el is not None:
            ts_el = sys_el.find(f"{{{ns}}}TimeCreated")
            if ts_el is not None:
                entry.timestamp = _parse_timestamp(ts_el.get("SystemTime", ""))

            lvl_el = sys_el.find(f"{{{ns}}}Level")
            if lvl_el is not None:
                entry.level = level_map.get(lvl_el.text or "", "INFO")

            comp_el = sys_el.find(f"{{{ns}}}Computer")
            if comp_el is not None:
                entry.hostname = comp_el.text

            exec_el = sys_el.find(f"{{{ns}}}Execution")
            if exec_el is not None:
                try:
                    entry.pid = int(exec_el.get("ProcessID", 0))
                    entry.tid = exec_el.get("ThreadID", "")
                except (ValueError, TypeError):
                    pass

            provider_el = sys_el.find(f"{{{ns}}}Provider")
            if provider_el is not None:
                entry.extra_fields["provider"] = provider_el.get("Name", "")

            eid_el = sys_el.find(f"{{{ns}}}EventID")
            if eid_el is not None:
                entry.error_code = f"EventID:{eid_el.text}"

        data_el = root.find(f"{{{ns}}}EventData")
        if data_el is not None:
            parts = []
            for child in data_el:
                name = child.get("Name", "")
                val = (child.text or "").strip()
                if name:
                    parts.append(f"{name}={val}")
                    entry.extra_fields[name] = val
                elif val:
                    parts.append(val)
            entry.message = " | ".join(parts)

        entry.raw_line = xml_str[:200]
        return entry

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        return None

    def parse_lines(self, lines: list[str], source_file: str) -> list[LogEntry]:
        return []
