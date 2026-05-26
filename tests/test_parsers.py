"""Parser unit tests — run with: python -m pytest tests/"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime

from app.parsers.generic_parser import GenericParser
from app.parsers.json_parser import JsonParser
from app.parsers.syslog_parser import SyslogParser
from app.parsers.apache_parser import ApacheAccessParser, NginxAccessParser
from app.parsers.java_parser import JavaParser
from app.parsers.docker_parser import DockerParser
from app.parsers.auto_detector import AutoDetector
from app.parsers.base_parser import BaseParser


@pytest.fixture(autouse=True)
def reset_counter():
    BaseParser.reset_counter()
    yield


class TestGenericParser:
    def test_iso_timestamp(self):
        p = GenericParser()
        entries = p.parse_lines(["2024-01-15 10:30:45.123 ERROR Something failed"], "test.log")
        assert len(entries) == 1
        e = entries[0]
        assert e.timestamp is not None
        assert e.timestamp.year == 2024
        assert e.level == "ERROR"
        assert "Something failed" in e.message

    def test_no_timestamp(self):
        p = GenericParser()
        entries = p.parse_lines(["Just a plain log line with no timestamp"], "test.log")
        assert len(entries) == 1
        assert entries[0].message == "Just a plain log line with no timestamp"

    def test_level_detection(self):
        p = GenericParser()
        for level in ["TRACE", "DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"]:
            entries = p.parse_lines([f"2024-01-15 10:00:00 {level} test message"], "test.log")
            assert entries[0].level == level

    def test_empty_lines_skipped(self):
        p = GenericParser()
        entries = p.parse_lines(["", "   ", "\t", "2024-01-15 10:00:00 INFO real line"], "t.log")
        assert len(entries) == 1


class TestJsonParser:
    def test_basic_json(self):
        p = JsonParser()
        line = '{"timestamp":"2024-01-15T10:00:00Z","level":"ERROR","message":"DB down","hostname":"server1"}'
        entries = p.parse_lines([line], "test.jsonl")
        assert len(entries) == 1
        e = entries[0]
        assert e.level == "ERROR"
        assert e.message == "DB down"
        assert e.hostname == "server1"

    def test_docker_json_keys(self):
        p = JsonParser()
        line = '{"ts":1705312800,"lvl":"warn","msg":"high memory usage","pid":1234}'
        entries = p.parse_lines([line], "test.jsonl")
        assert len(entries) == 1
        assert "WARN" in entries[0].level or entries[0].level == "WARN"

    def test_invalid_json_skipped(self):
        p = JsonParser()
        entries = p.parse_lines(["{invalid json}"], "test.jsonl")
        assert len(entries) == 0

    def test_probe_pure_json(self):
        p = JsonParser()
        lines = ['{"a":1}', '{"b":2}', '{"c":3}']
        assert p.probe(lines) >= 0.9


class TestSyslogParser:
    def test_rfc3164(self):
        p = SyslogParser()
        line = "<13>Jan 15 10:00:01 myhost sshd[1234]: Accepted password"
        entries = p.parse_lines([line], "syslog")
        assert len(entries) == 1
        e = entries[0]
        assert e.hostname == "myhost"
        assert e.pid == 1234

    def test_plain_syslog(self):
        p = SyslogParser()
        line = "Jan 15 10:00:01 myhost kernel: Out of memory"
        entries = p.parse_lines([line], "syslog")
        assert len(entries) == 1
        assert entries[0].hostname == "myhost"
        assert "Out of memory" in entries[0].message


class TestApacheParser:
    def test_access_log(self):
        p = ApacheAccessParser()
        line = '192.168.1.1 - john [15/Jan/2024:10:00:01 +0000] "GET /index HTTP/1.1" 200 1234'
        entries = p.parse_lines([line], "access.log")
        assert len(entries) == 1
        e = entries[0]
        assert e.hostname == "192.168.1.1"
        assert e.user == "john"
        assert e.extra_fields.get("status") == "200"

    def test_500_is_error(self):
        p = ApacheAccessParser()
        line = '10.0.0.1 - - [15/Jan/2024:10:00:01 +0000] "GET /bad HTTP/1.1" 500 64'
        entries = p.parse_lines([line], "access.log")
        assert entries[0].level == "ERROR"


class TestJavaParser:
    def test_spring_boot(self):
        p = JavaParser()
        line = "2024-01-15 10:00:00.123  ERROR 9999 --- [main] com.example.App : Connection refused"
        entries = p.parse_lines([line], "app.log")
        assert len(entries) == 1
        e = entries[0]
        assert e.level == "ERROR"
        assert e.pid == 9999
        assert "Connection refused" in e.message

    def test_multiline_stacktrace(self):
        p = JavaParser()
        lines = [
            "2024-01-15 10:00:00.000  ERROR 100 --- [main] c.e.App : NullPointerException",
            "    at com.example.App.main(App.java:42)",
            "    at sun.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:62)",
        ]
        entries = p.parse_lines(lines, "app.log")
        assert len(entries) == 1
        assert "at com.example" in entries[0].message


class TestDockerParser:
    def test_docker_json(self):
        p = DockerParser()
        line = '{"log":"2024-01-15T10:00:00Z ERROR Service unavailable\\n","stream":"stderr","time":"2024-01-15T10:00:00Z"}'
        entries = p.parse_lines([line], "container.log")
        assert len(entries) == 1
        assert "Service unavailable" in entries[0].message


class TestFieldExtractor:
    def test_ip_extraction(self):
        from app.parsers.base_parser import FieldExtractor
        from app.core.models import LogEntry
        e = LogEntry(raw_line="Connection from 192.168.1.100 to 10.0.0.1", message="test")
        FieldExtractor.enrich(e)
        assert "192.168.1.100" in e.ip_addresses

    def test_uuid_as_correlation(self):
        from app.parsers.base_parser import FieldExtractor
        from app.core.models import LogEntry
        e = LogEntry(raw_line="Request 550e8400-e29b-41d4-a716-446655440000 failed", message="t")
        FieldExtractor.enrich(e)
        assert e.correlation_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_url_extraction(self):
        from app.parsers.base_parser import FieldExtractor
        from app.core.models import LogEntry
        e = LogEntry(raw_line="Calling https://api.example.com/v1/orders", message="t")
        FieldExtractor.enrich(e)
        assert any("api.example.com" in u for u in e.urls)


class TestAutoDetector:
    def test_detect_json(self):
        d = AutoDetector()
        sample = ['{"level":"info","msg":"test"}'] * 10
        parser = d.detect("test.jsonl", sample)
        assert parser.name == "json"

    def test_detect_apache(self):
        d = AutoDetector()
        sample = ['192.168.1.1 - - [15/Jan/2024:10:00:01 +0000] "GET / HTTP/1.1" 200 1234'] * 10
        parser = d.detect("access.log", sample)
        assert "apache" in parser.name or "nginx" in parser.name

    def test_detect_fallback_generic(self):
        d = AutoDetector()
        sample = ["totally random text with no structure"] * 10
        parser = d.detect("weird.log", sample)
        assert parser.name == "generic"


class TestSearchIndex:
    def test_insert_and_retrieve(self):
        from app.search.indexer import LogIndex
        from app.core.models import LogEntry
        from datetime import datetime
        idx = LogIndex()
        e = LogEntry(id=1, level="ERROR", message="database down", source_file="app.log",
                     raw_line="2024 ERROR database down", timestamp=datetime(2024, 1, 15, 10, 0))
        idx.insert_batch([e])
        assert idx.total_count() == 1

    def test_filter_by_level(self):
        from app.search.indexer import LogIndex
        from app.core.models import LogEntry, FilterState
        from datetime import datetime
        idx = LogIndex()
        entries = [
            LogEntry(id=i, level="INFO" if i % 2 == 0 else "ERROR",
                     message=f"msg {i}", source_file="t.log", raw_line=f"line {i}")
            for i in range(1, 11)
        ]
        idx.insert_batch(entries)
        f = FilterState(levels=["ERROR"])
        count = idx.count_filtered(f)
        assert count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
