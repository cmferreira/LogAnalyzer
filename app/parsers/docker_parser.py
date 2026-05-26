from __future__ import annotations
import json
import re
from typing import Optional

from app.core.models import LogEntry
from app.parsers.base_parser import BaseParser
from app.parsers.generic_parser import _parse_timestamp

# Docker JSON log line: {"log":"...\n","stream":"stdout","time":"2024-01-15T10:30:45.123Z"}
_DOCKER_JSON_KEYS = {"log", "stream", "time"}

# Kubernetes log: 2024-01-15T10:30:45.123Z stderr F [ERROR] message
_K8S = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.,\d]*Z?)\s+"
    r"(stdout|stderr)\s+[FP]\s+(.*)"
)

_LEVEL_RE = re.compile(
    r"\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|ERR|CRITICAL|FATAL)\b",
    re.IGNORECASE,
)


class DockerParser(BaseParser):
    name = "docker"
    supported_extensions = [".log", ".json"]

    def probe(self, sample_lines: list[str]) -> float:
        hits = 0
        for line in sample_lines[:20]:
            line = line.strip()
            if not line:
                continue
            if line.startswith("{"):
                try:
                    d = json.loads(line)
                    if isinstance(d, dict) and _DOCKER_JSON_KEYS & set(d.keys()):
                        hits += 1
                        continue
                except json.JSONDecodeError:
                    pass
            if _K8S.match(line):
                hits += 1
        total = len([l for l in sample_lines[:20] if l.strip()])
        return min(0.9, hits / max(total, 1))

    def _parse_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        stripped = line.strip()

        # Docker JSON format
        if stripped.startswith("{"):
            try:
                d = json.loads(stripped)
                if isinstance(d, dict) and "log" in d:
                    entry = LogEntry()
                    entry.timestamp = _parse_timestamp(d.get("time", ""))
                    log_text = d["log"].rstrip("\n")
                    lm = _LEVEL_RE.search(log_text)
                    entry.level = lm.group(1).upper() if lm else "INFO"
                    entry.extra_fields["stream"] = d.get("stream", "")
                    entry.message = log_text
                    return entry
            except json.JSONDecodeError:
                pass

        # Kubernetes format
        m = _K8S.match(stripped)
        if m:
            entry = LogEntry()
            entry.timestamp = _parse_timestamp(m.group(1))
            stream = m.group(2)
            entry.level = "ERROR" if stream == "stderr" else "INFO"
            msg = m.group(3)
            lm = _LEVEL_RE.search(msg)
            if lm:
                entry.level = lm.group(1).upper()
            entry.message = msg
            return entry

        return None


class K8sParser(DockerParser):
    name = "k8s"
    supported_extensions = [".log"]
