import json
import logging
import os
import sys
from datetime import datetime, timezone

from app.core.config import get_settings

settings = get_settings()

# ── ANSI codes ────────────────────────────────────────────────────────────────
_R  = "\033[0m"   # reset
_B  = "\033[1m"   # bold
_D  = "\033[2m"   # dim

_GRN  = "\033[32m" 
_BGRN = "\033[92m"
_YLW  = "\033[33m"  
_BYLW = "\033[93m"
_RED  = "\033[31m"  
_BRED = "\033[91m"
_CYN  = "\033[36m"
_BCYN = "\033[96m"
_BLU  = "\033[34m"
_BBLU = "\033[94m"
_WHT  = "\033[37m"
_BWHT = "\033[97m"

_LEVEL_STYLES: dict[int, tuple[str, str]] = {
    logging.DEBUG:    (_D + _CYN,  "DBG"),
    logging.INFO:     (_WHT,       "INF"),
    logging.WARNING:  (_BYLW,      "WRN"),
    logging.ERROR:    (_BRED,      "ERR"),
    logging.CRITICAL: (_B + _BRED, "CRT"),
}

_METHOD_COLORS: dict[str, str] = {
    "GET":     _BGRN,
    "POST":    _BBLU,
    "PUT":     _BYLW,
    "PATCH":   _BCYN,
    "DELETE":  _BRED,
    "HEAD":    _CYN,
    "OPTIONS": _D + _WHT,
}


def _status_color(code: int) -> str:
    if 200 <= code < 300:
        return _BGRN
    if 300 <= code < 400:
        return _BCYN
    if 400 <= code < 500:
        return _BYLW
    return _BRED


def _duration_color(ms: float) -> str:
    if ms < 150:  
        return _BGRN
    if ms < 500:  
        return _BYLW
    return _BRED


def _short_name(name: str, width: int = 16) -> str:
    parts = name.split(".")
    short = ".".join(parts[-2:]) if len(parts) > 1 else name
    return short[:width]


class ColoredFormatter(logging.Formatter):
    """
    Two rendering modes:
      • Records with req_status extra → compact coloured HTTP request line.
      • Everything else               → coloured level/name/message line.
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%H:%M:%S")

        # ── HTTP request line ────────────────────────────────────────────────
        if hasattr(record, "req_status"):
            method = getattr(record, "req_method", "???")
            path   = getattr(record, "req_path",   "")
            status = getattr(record, "req_status",  0)
            ms     = getattr(record, "req_ms",      0.0)
            rid    = getattr(record, "req_id",      "")

            mc = _METHOD_COLORS.get(method, _WHT)
            sc = _status_color(status)
            dc = _duration_color(ms)

            m_s = f"{mc}{_B}{method:<7}{_R}"
            p_s = f"{_BWHT}{path}{_R}"
            s_s = f"{sc}{_B}{status}{_R}"
            d_s = f"{dc}{ms}ms{_R}"
            r_s = f"{_D}{rid[:8]}{_R}"

            return f"{_D}{ts}{_R}  {m_s} {p_s:<50} {s_s}  {d_s:<14} {_D}▸{_R} {r_s}"

        # ── Standard log line ────────────────────────────────────────────────
        clr, badge = _LEVEL_STYLES.get(record.levelno, (_WHT, "INF"))
        name_s = f"{_D}{_short_name(record.name):<16}{_R}"
        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)

        return f"{_D}{ts}{_R}  {clr}{badge}{_R}  {name_s}  {clr}{msg}{_R}"


class PlainFormatter(logging.Formatter):
    """Fallback for non-TTY / NO_COLOR environments."""

    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, self._DATE_FMT)

        if hasattr(record, "req_status"):
            method = getattr(record, "req_method", "???")
            path   = getattr(record, "req_path",   "")
            status = getattr(record, "req_status",  0)
            ms     = getattr(record, "req_ms",      0.0)
            rid    = getattr(record, "req_id",      "")
            return f"{ts} | {record.levelname:<8} | {record.name} | {method} {path} {status} {ms}ms req:{rid}"

        msg = record.getMessage()
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return f"{ts} | {record.levelname:<8} | {record.name} | {msg}"


class JsonFormatter(logging.Formatter):
    """
    Newline-delimited JSON (one object per line).
    Designed for CloudWatch Logs Insights, Datadog, Loki, GCP Logging, etc.

    Activate with:  LOG_FORMAT=json
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3] + "Z"

        doc: dict = {
            "ts":     ts,
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }

        if hasattr(record, "req_status"):
            doc["req_id"]     = getattr(record, "req_id",     "")
            doc["req_method"] = getattr(record, "req_method", "")
            doc["req_path"]   = getattr(record, "req_path",   "")
            doc["req_status"] = getattr(record, "req_status",  0)
            doc["req_ms"]     = getattr(record, "req_ms",      0.0)

        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)

        return json.dumps(doc, ensure_ascii=False)


def _pick_formatter() -> logging.Formatter:
    log_format = os.getenv("LOG_FORMAT", "").lower()
    if log_format == "json":
        return JsonFormatter()
    if os.getenv("NO_COLOR") or os.getenv("TERM") == "dumb" or not sys.stdout.isatty():
        return PlainFormatter()
    return ColoredFormatter()


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_pick_formatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)