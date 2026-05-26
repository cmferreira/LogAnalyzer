APP_NAME = "LogAnalyzer"
APP_VERSION = "1.0.0"

LEVELS_ORDERED = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "CRITICAL", "FATAL"]

LEVEL_COLORS_DARK = {
    "TRACE":    ("#888888", "#1a1a1a"),
    "DEBUG":    ("#aaaaaa", "#1a1a1a"),
    "INFO":     ("#d4d4d4", "#1a1a1a"),
    "WARN":     ("#f0c040", "#2a2000"),
    "WARNING":  ("#f0c040", "#2a2000"),
    "ERROR":    ("#ff6b6b", "#2d0000"),
    "ERR":      ("#ff6b6b", "#2d0000"),
    "CRITICAL": ("#ff4444", "#3a0000"),
    "FATAL":    ("#ff2222", "#450000"),
    "":         ("#d4d4d4", "#1a1a1a"),
}

LEVEL_COLORS_LIGHT = {
    "TRACE":    ("#888888", "#f8f8f8"),
    "DEBUG":    ("#666666", "#f0f0f0"),
    "INFO":     ("#1a1a1a", "#ffffff"),
    "WARN":     ("#7a5500", "#fff8e0"),
    "WARNING":  ("#7a5500", "#fff8e0"),
    "ERROR":    ("#cc0000", "#fff0f0"),
    "ERR":      ("#cc0000", "#fff0f0"),
    "CRITICAL": ("#aa0000", "#ffe0e0"),
    "FATAL":    ("#880000", "#ffd0d0"),
    "":         ("#1a1a1a", "#ffffff"),
}

CHUNK_SIZE = 15_000
PAGE_CACHE_SIZE = 10
PAGE_SIZE = 500
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB
TAIL_POLL_INTERVAL_MS = 500
MAX_RECENT_FILES = 20
MAX_SEARCH_HISTORY = 50
