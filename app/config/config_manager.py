from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Any


def _app_dir() -> Path:
    """Return the directory containing the executable (or script in dev mode)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


class ConfigManager:
    _instance: "ConfigManager | None" = None

    def __init__(self) -> None:
        self._path = _app_dir() / "config.json"
        self._data: dict[str, Any] = {}
        self._load()

    @classmethod
    def instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = ConfigManager()
        return cls._instance

    def _defaults(self) -> dict[str, Any]:
        return {
            "theme": "dark",
            "recent_files": [],
            "search_history": [],
            "filter_presets": [],
            "window": {"x": 100, "y": 100, "width": 1400, "height": 900, "maximized": False},
            "last_folder": "",
            "auto_scroll": True,
            "chunk_size": 5000,
            "tail_interval_ms": 500,
            "correlation_window_before_s": 300,
            "correlation_window_after_s": 600,
            "max_recent_files": 20,
            "show_raw_column": True,
            "splitter_sizes": [],
        }

    def _load(self) -> None:
        self._data = self._defaults()
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                self._data.update(stored)
            except Exception:
                pass

    def save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def add_recent_file(self, path: str) -> None:
        recents: list[str] = self._data.get("recent_files", [])
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        max_r = self._data.get("max_recent_files", 20)
        self._data["recent_files"] = recents[:max_r]

    def add_search_history(self, text: str) -> None:
        history: list[str] = self._data.get("search_history", [])
        if text in history:
            history.remove(text)
        history.insert(0, text)
        self._data["search_history"] = history[:50]

    @property
    def theme(self) -> str:
        return self._data.get("theme", "dark")

    @theme.setter
    def theme(self, value: str) -> None:
        self._data["theme"] = value
