from __future__ import annotations
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp


class XmlParser(BaseParser):
    name = "xml"
    supported_extensions = [".xml", ".evtx"]

    def probe(self, sample_lines: list[str]) -> float:
        joined = " ".join(sample_lines[:10])
        if "<?xml" in joined or "<Events" in joined or "<Event " in joined:
            return 0.85
        if joined.strip().startswith("<"):
            return 0.4
        return 0.0

    def parse_lines(self, lines: list[str], source_file: str) -> list[LogEntry]:
        try:
            from lxml import etree
        except ImportError:
            import xml.etree.ElementTree as etree  # type: ignore

        content = "\n".join(lines)
        entries: list[LogEntry] = []

        try:
            root = etree.fromstring(content.encode("utf-8"))
        except Exception:
            # Try wrapping in a root element
            try:
                root = etree.fromstring(f"<root>{content}</root>".encode("utf-8"))
            except Exception:
                return []

        # Windows Event Log XML
        ns = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
        events = root.findall(".//e:Event", ns) or root.findall(".//Event")

        for event in events:
            entry = self._parse_event_xml(event, ns, source_file)
            if entry:
                entry.id = self._next_id()
                entry.source_file = source_file
                from app.parsers.base_parser import FieldExtractor
                FieldExtractor.enrich(entry)
                entries.append(entry)

        if not entries:
            # Generic XML: each child element = one log entry
            for child in root:
                entry = LogEntry(
                    id=self._next_id(),
                    source_file=source_file,
                    message=str(child.text or "").strip(),
                    raw_line=str(child.tag),
                )
                entries.append(entry)

        return entries

    def _parse_event_xml(self, event, ns: dict, source_file: str) -> Optional[LogEntry]:
        entry = LogEntry()

        def find_text(tag: str) -> str:
            el = event.find(f".//{{{ns.get('e', '')}}}{{tag}}") if ns.get("e") else None
            if el is None:
                el = event.find(f".//{tag}")
            return (el.text or "").strip() if el is not None else ""

        # System section
        sys_el = event.find("{http://schemas.microsoft.com/win/2004/08/events/event}System") \
                 or event.find("System")
        if sys_el is not None:
            ts_el = sys_el.find("{http://schemas.microsoft.com/win/2004/08/events/event}TimeCreated") \
                    or sys_el.find("TimeCreated")
            if ts_el is not None:
                ts_str = ts_el.get("SystemTime", "")
                entry.timestamp = _parse_timestamp(ts_str) if ts_str else None

            level_el = sys_el.find("{http://schemas.microsoft.com/win/2004/08/events/event}Level") \
                       or sys_el.find("Level")
            if level_el is not None:
                level_map = {"1": "CRITICAL", "2": "ERROR", "3": "WARN", "4": "INFO", "5": "DEBUG"}
                entry.level = level_map.get(level_el.text or "", "INFO")

            comp_el = sys_el.find("{http://schemas.microsoft.com/win/2004/08/events/event}Computer") \
                      or sys_el.find("Computer")
            if comp_el is not None:
                entry.hostname = comp_el.text

            pid_el = sys_el.find(".//{http://schemas.microsoft.com/win/2004/08/events/event}Execution") \
                     or sys_el.find(".//Execution")
            if pid_el is not None:
                try:
                    entry.pid = int(pid_el.get("ProcessID", 0))
                    entry.tid = pid_el.get("ThreadID", "")
                except (ValueError, TypeError):
                    pass

        # EventData section
        data_el = event.find("{http://schemas.microsoft.com/win/2004/08/events/event}EventData") \
                  or event.find("EventData")
        if data_el is not None:
            parts = []
            for data in data_el:
                name = data.get("Name", "")
                val = (data.text or "").strip()
                if name:
                    parts.append(f"{name}={val}")
                    entry.extra_fields[name] = val
                elif val:
                    parts.append(val)
            entry.message = " | ".join(parts)

        entry.raw_line = ""
        return entry

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        return None
