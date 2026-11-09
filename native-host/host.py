#!/usr/bin/env python3
"""yt-dlp Extension Native Messaging host.

Communicates with the browser extension over stdio using the Chrome Native
Messaging protocol (4-byte little-endian length prefix + UTF-8 JSON).

Never prints debug to stdout; diagnostics go to stderr only.
All yt-dlp invocations use subprocess argument arrays (shell=False).
"""

from __future__ import annotations

import json
import logging
import os
import struct
import sys
import threading
from typing import Any

# Allow running both as a script and as a module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CONFIG_PATH, ensure_config_dir, load_config, save_config  # noqa: E402
from downloader import DownloadManager  # noqa: E402
from formats import discover_formats, is_video_url  # noqa: E402

HOST_NAME = "com.yt-dlp-extension.host"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger(HOST_NAME)

SHUTDOWN = threading.Event()


# ---------------------------------------------------------------------- #
# Native Messaging framing
# ---------------------------------------------------------------------- #
def read_message() -> dict[str, Any] | None:
    """Read one framed message from stdin. Returns None on clean EOF."""
    try:
        raw_length = sys.stdin.buffer.read(4)
    except OSError:
        return None
    if not raw_length or len(raw_length) < 4:
        return None
    (length,) = struct.unpack("<I", raw_length)
    if length == 0 or length > 10 * 1024 * 1024:  # 10 MB sanity cap
        return None
    try:
        raw = sys.stdin.buffer.read(length)
    except OSError:
        return None
    if len(raw) < length:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        log.warning("Received malformed JSON from extension")
        return None


def send_message(message: dict[str, Any]) -> None:
    """Send one framed JSON message to stdout."""
    payload = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(payload)))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def send_error(code: str, message: str) -> None:
    send_message({"type": "error", "code": code, "message": message})


# ---------------------------------------------------------------------- #
# Handlers
# ---------------------------------------------------------------------- #
def handle_ping() -> None:
    send_message({"type": "pong", "ok": True})


def handle_metadata(message: dict[str, Any]) -> None:
    url = message.get("url")
    if not isinstance(url, str) or not is_video_url(url):
        send_message({"type": "metadata_result", "ok": False, "error": "Invalid URL"})
        return
    try:
        from formats import _run_yt_dlp_json  # noqa: PLC0415
        info = _run_yt_dlp_json(url)
        metadata = {
            "title": info.get("title"),
            "channel": info.get("channel") or info.get("uploader"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "view_count": info.get("view_count"),
            "upload_date": info.get("upload_date"),
            "webpage_url": info.get("webpage_url") or url,
        }
        send_message({"type": "metadata_result", "ok": True, "data": metadata})
    except Exception as exc:  # noqa: BLE001
        log.exception("metadata extraction failed")
        send_message({"type": "metadata_result", "ok": False, "error": str(exc)})


def handle_formats(message: dict[str, Any]) -> None:
    url = message.get("url")
    if not isinstance(url, str) or not is_video_url(url):
        send_message({"type": "formats_result", "ok": False, "error": "Invalid URL"})
        return
    try:
        result = discover_formats(url)
        send_message({"type": "formats_result", "ok": True, "data": result})
    except Exception as exc:  # noqa: BLE001
        log.exception("format discovery failed")
        send_message({"type": "formats_result", "ok": False, "error": str(exc)})


def handle_download(message: dict[str, Any], manager: DownloadManager) -> None:
    try:
        download_id = manager.start_download(message)
    except ValueError as exc:
        send_message({"type": "download_failed", "download_id": "", "error": str(exc)})
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("failed to start download")
        send_message({"type": "download_failed", "download_id": "", "error": str(exc)})
        return
    send_message({"type": "download_started", "download_id": download_id})


def handle_cancel(message: dict[str, Any], manager: DownloadManager) -> None:
    download_id = message.get("download_id")
    if not isinstance(download_id, str):
        send_error("invalid_request", "missing download_id")
        return
    ok = manager.cancel_download(download_id)
    send_message({"type": "download_failed", "download_id": download_id, "error": "cancelled"} if ok else
                 {"type": "error", "code": "not_found", "message": "download not found"})


def handle_list(message: dict[str, Any], manager: DownloadManager) -> None:
    filter_ = message.get("filter", "all")
    if filter_ not in ("all", "active", "completed", "failed", "cancelled"):
        filter_ = "all"
    records = manager.list_downloads(filter_)
    send_message({"type": "list_result", "ok": True, "filter": filter_, "data": records})


def handle_config(message: dict[str, Any]) -> None:
    action = message.get("action")
    if action == "get":
        send_message({"type": "config_result", "ok": True, "data": load_config()})
    elif action == "set":
        updates = message.get("config")
        if not isinstance(updates, dict):
            send_error("invalid_request", "config must be an object")
            return
        cfg = load_config()
        cfg.update(updates)
        save_config(cfg)
        send_message({"type": "config_result", "ok": True, "data": cfg})
    else:
        send_error("invalid_request", "unknown config action")


# ---------------------------------------------------------------------- #
# Main loop
# ---------------------------------------------------------------------- #
HANDLERS = {
    "ping": lambda m=None, grp=None: handle_ping(),
    "metadata": handle_metadata,
    "formats": handle_formats,
    "download": handle_download,
    "cancel": handle_cancel,
    "list": handle_list,
    "config": handle_config,
}


def main() -> None:
    log.info("Native messaging host %s starting", HOST_NAME)
    manager = DownloadManager(send_message)

    while not SHUTDOWN.is_set():
        message = read_message()
        if message is None:
            break  # EOF / browser disconnected

        if not isinstance(message, dict):
            send_error("invalid_request", "message must be a JSON object")
            continue

        msg_type = message.get("type")
        handler = HANDLERS.get(msg_type)
        if handler is None:
            send_error("unknown_type", f"unknown message type: {msg_type!r}")
            continue

        try:
            if msg_type in ("download", "cancel", "list"):
                handler(message, manager)
            elif msg_type == "config":
                handle_config(message)
            else:
                handler(message)
        except Exception as exc:  # noqa: BLE001
            log.exception("handler error for %s", msg_type)
            send_error("internal_error", str(exc))

    log.info("Native messaging host %s shutting down", HOST_NAME)


if __name__ == "__main__":
    main()
