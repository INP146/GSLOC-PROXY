from __future__ import annotations

import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Any


LOG_LEVEL_VALUES = {
    "debug": 10,
    "info": 20,
    "success": 25,
    "warning": 30,
    "error": 40,
}

DEFAULT_LOG_LEVEL = "info"
DEFAULT_LOG_FORMAT = "jsonl"
ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_COLORS = {
    "time": "\033[38;5;67m",
    "info": "\033[38;5;39m",
    "success": "\033[38;5;120m",
    "warning": "\033[38;5;229m",
    "error": "\033[38;5;217m",
    "layer": "\033[38;5;177m",
    "source": "\033[38;5;109m",
    "method": "\033[38;5;75m",
    "host": "\033[38;5;50m",
    "path": "\033[38;5;214m",
    "status": "\033[38;5;121m",
    "client": "\033[38;5;121m",
    "type": "\033[38;5;212m",
    "message": "\033[38;5;254m",
    "details": "\033[38;5;245m",
}


def normalize_log_level(level: str | None) -> str:
    normalized = (level or DEFAULT_LOG_LEVEL).strip().lower()
    if normalized == "warn":
        normalized = "warning"
    if normalized not in LOG_LEVEL_VALUES:
        return DEFAULT_LOG_LEVEL
    return normalized


def log_level_value(level: str | None) -> int:
    return LOG_LEVEL_VALUES[normalize_log_level(level)]


def should_emit_log(level: str | None, minimum_level: str | None) -> bool:
    return log_level_value(level) >= log_level_value(minimum_level)


def normalize_log_format(log_format: str | None) -> str:
    normalized = (log_format or DEFAULT_LOG_FORMAT).strip().lower()
    if normalized in ("text", "plain"):
        return "text"
    return DEFAULT_LOG_FORMAT


def format_log_record(record: dict[str, Any]) -> str:
    timestamp = datetime.fromtimestamp(float(record.get("ts", 0))).strftime("%Y-%m-%d %H:%M:%S")
    level = normalize_log_level(str(record.get("level") or "info")).upper().ljust(7)
    logger = record.get("logger") or "gsloc-proxy"
    layer = record.get("layer") or "system"
    parts = [timestamp, level, f"{logger}[{layer}]"]

    session_id = record.get("session_id")
    if session_id is not None:
        parts.append(f"session={session_id}")

    source = record.get("source")
    if source:
        parts.append(str(source))

    request_bits = " ".join(
        str(bit)
        for bit in (record.get("method"), record.get("host"), record.get("path"))
        if bit
    )
    if request_bits:
        parts.append(request_bits)

    status = record.get("status")
    if status is not None:
        parts.append(f"status={status}")

    client = record.get("client")
    if client:
        parts.append(f"client={client}")

    log_type = record.get("type") or "log"
    message = record.get("message") or ""
    parts.append(f"{log_type}: {message}")
    return " ".join(parts)


def format_log_record_jsonl(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def _compact_details(details: Any) -> str:
    if not isinstance(details, dict):
        return ""
    parts = []
    for key, value in details.items():
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list, tuple)):
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return " ".join(parts)


def _color(text: str, token: str, *, enabled: bool, bold: bool = False) -> str:
    if not enabled or not text:
        return text
    style = ANSI_COLORS.get(token, "")
    weight = ANSI_BOLD if bold else ""
    return f"{weight}{style}{text}{ANSI_RESET}"


def format_log_record_terminal(record: dict[str, Any], *, color: bool = False) -> str:
    timestamp = datetime.fromtimestamp(float(record.get("ts", 0))).strftime("%Y-%m-%d %H:%M:%S")
    level = normalize_log_level(str(record.get("level") or "info"))
    logger = record.get("logger") or "gsloc-proxy"
    layer = record.get("layer") or "system"
    parts = [
        _color(timestamp, "time", enabled=color),
        " ",
        _color(level.upper().ljust(7), level, enabled=color, bold=True),
        " ",
        _color(f"{logger}[{layer}]", "layer", enabled=color, bold=True),
    ]

    session_id = record.get("session_id")
    if session_id is not None:
        parts.extend([" ", _color(f"session={session_id}", "source", enabled=color)])

    source = record.get("source")
    if source:
        parts.extend([" ", _color(str(source), "source", enabled=color)])

    if record.get("method") or record.get("host") or record.get("path"):
        parts.append(" - ")
        method = record.get("method")
        if method:
            parts.extend([_color(str(method), "method", enabled=color, bold=True), " "])
        host = record.get("host")
        if host:
            parts.extend([_color(str(host), "host", enabled=color), " "])
        path = record.get("path")
        if path:
            parts.append(_color(str(path), "path", enabled=color))

    status = record.get("status")
    if status is not None:
        parts.extend([" ", _color(f"status={status}", "status", enabled=color)])
    client = record.get("client")
    if client:
        parts.extend([" ", _color(f"client={client}", "client", enabled=color)])

    log_type = record.get("type") or "log"
    message = record.get("message") or ""
    parts.extend(
        [
            " - ",
            _color(f"{log_type}:", "type", enabled=color, bold=True),
            " ",
            _color(str(message), "message", enabled=color),
        ]
    )

    details = _compact_details(record.get("details"))
    if details:
        parts.extend([" ", _color(details, "details", enabled=color)])

    return "".join(parts)


class GslocTerminalLogSink:
    def __init__(self, *, level: str = DEFAULT_LOG_LEVEL) -> None:
        self.level = normalize_log_level(level)
        self.color = "NO_COLOR" not in os.environ

    def emit(self, record: dict[str, Any]) -> None:
        if not should_emit_log(str(record.get("level") or "info"), self.level):
            return
        record_level = normalize_log_level(str(record.get("level") or "info"))
        stream = sys.stderr if record_level in ("warning", "error") else sys.stdout
        line = format_log_record_terminal(record, color=self.color)
        print(line, file=stream, flush=True)


class GslocFileLogSink:
    def __init__(
        self,
        path: str | Path,
        *,
        level: str = DEFAULT_LOG_LEVEL,
        log_format: str = DEFAULT_LOG_FORMAT,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ) -> None:
        self.path = Path(path).expanduser()
        self.level = normalize_log_level(level)
        self.log_format = normalize_log_format(log_format)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handler = RotatingFileHandler(
            self.path,
            maxBytes=max(0, int(max_bytes)),
            backupCount=max(0, int(backup_count)),
            encoding="utf-8",
        )
        self.handler.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: dict[str, Any]) -> None:
        if not should_emit_log(str(record.get("level") or "info"), self.level):
            return
        line = (
            format_log_record(record)
            if self.log_format == "text"
            else format_log_record_jsonl(record)
        )
        self.handler.emit(
            logging.makeLogRecord(
                {
                    "name": "gsloc-proxy.file",
                    "levelno": logging.INFO,
                    "levelname": "INFO",
                    "msg": line,
                    "args": (),
                }
            )
        )

    def close(self) -> None:
        self.handler.close()
