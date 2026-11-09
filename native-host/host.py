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
import subprocess
import sys
import threading
from typing import Any

# Allow running both as a script and as a module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_DOWNLOAD_DIR, load_config, save_config  # noqa: E402
from downloader import DownloadManager  # noqa: E402
from formats import discover_formats, get_media_info, is_video_url  # noqa: E402

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
def read_message(stream=None) -> dict[str, Any] | None:
    """Read one framed message from stream (default stdin.buffer). Returns None on clean EOF."""
    s = stream or sys.stdin.buffer
    try:
        raw_length = s.read(4)
    except OSError:
        return None
    if not raw_length or len(raw_length) < 4:
        return None
    (length,) = struct.unpack("<I", raw_length)
    if length == 0 or length > 10 * 1024 * 1024:  # 10 MB sanity cap
        return None
    try:
        raw = s.read(length)
    except OSError:
        return None
    if len(raw) < length:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        log.warning("Received malformed JSON from extension")
        return None


def send_message(message: dict[str, Any], stream=None) -> None:
    """Send one framed JSON message to stream (default stdout.buffer)."""
    s = stream or sys.stdout.buffer
    payload = json.dumps(message).encode("utf-8")
    s.write(struct.pack("<I", len(payload)))
    s.write(payload)
    s.flush()


def send_reply(orig_msg: dict[str, Any], payload: dict[str, Any]) -> None:
    """Send a reply, automatically echoing req_id if provided in orig_msg."""
    if "req_id" in orig_msg and "req_id" not in payload:
        payload["req_id"] = orig_msg["req_id"]
    send_message(payload)


def send_error(code: str, message: str, req_id: str | None = None) -> None:
    payload: dict[str, Any] = {"type": "error", "code": code, "message": message, "ok": False}
    if req_id is not None:
        payload["req_id"] = req_id
    send_message(payload)


# ---------------------------------------------------------------------- #
# Handlers
# ---------------------------------------------------------------------- #
def handle_ping(message: dict[str, Any]) -> None:
    send_reply(message, {"type": "pong", "ok": True})


def handle_media_info(message: dict[str, Any]) -> None:
    """Extract full media metadata and formats in a single pass."""
    url = message.get("url")
    if not isinstance(url, str) or not is_video_url(url):
        send_reply(message, {"type": "media_info_result", "ok": False, "error": "Invalid URL"})
        return
    try:
        info = get_media_info(url)
        send_reply(message, {"type": "media_info_result", "ok": True, "data": info})
    except Exception as exc:  # noqa: BLE001
        log.exception("media_info extraction failed")
        send_reply(message, {"type": "media_info_result", "ok": False, "error": str(exc)})


def handle_metadata(message: dict[str, Any]) -> None:
    url = message.get("url")
    if not isinstance(url, str) or not is_video_url(url):
        send_reply(message, {"type": "metadata_result", "ok": False, "error": "Invalid URL"})
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
        send_reply(message, {"type": "metadata_result", "ok": True, "data": metadata})
    except Exception as exc:  # noqa: BLE001
        log.exception("metadata extraction failed")
        send_reply(message, {"type": "metadata_result", "ok": False, "error": str(exc)})


def handle_formats(message: dict[str, Any]) -> None:
    url = message.get("url")
    if not isinstance(url, str) or not is_video_url(url):
        send_reply(message, {"type": "formats_result", "ok": False, "error": "Invalid URL"})
        return
    try:
        result = discover_formats(url)
        send_reply(message, {"type": "formats_result", "ok": True, "data": result})
    except Exception as exc:  # noqa: BLE001
        log.exception("format discovery failed")
        send_reply(message, {"type": "formats_result", "ok": False, "error": str(exc)})


def handle_download(message: dict[str, Any], manager: DownloadManager) -> None:
    req_id = message.get("req_id")
    try:
        download_id = manager.start_download(message)
    except ValueError as exc:
        send_reply(message, {"type": "download_failed", "download_id": "", "error": str(exc), "ok": False})
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("failed to start download")
        send_reply(message, {"type": "download_failed", "download_id": "", "error": str(exc), "ok": False})
        return
    send_reply(message, {"type": "download_started", "download_id": download_id, "ok": True})


def handle_cancel(message: dict[str, Any], manager: DownloadManager) -> None:
    download_id = message.get("download_id")
    if not isinstance(download_id, str):
        send_error("invalid_request", "missing download_id", message.get("req_id"))
        return
    ok = manager.cancel_download(download_id)
    send_reply(message, {
        "type": "cancel_result",
        "ok": ok,
        "download_id": download_id,
        "message": "cancelled" if ok else "download not found",
    })


def handle_list(message: dict[str, Any], manager: DownloadManager) -> None:
    filter_ = message.get("filter", "all")
    if filter_ not in ("all", "active", "completed", "failed", "cancelled"):
        filter_ = "all"
    records = manager.list_downloads(filter_)
    send_reply(message, {"type": "list_result", "ok": True, "filter": filter_, "data": records})


def handle_config(message: dict[str, Any]) -> None:
    action = message.get("action")
    if action == "get":
        cfg = load_config()
        send_reply(message, {
            "type": "config_result",
            "ok": True,
            "data": cfg,
            "defaults": {
                "download_dir": DEFAULT_DOWNLOAD_DIR,
            },
        })
    elif action == "set":
        updates = message.get("config")
        if not isinstance(updates, dict):
            send_error("invalid_request", "config must be an object", message.get("req_id"))
            return
        cfg = load_config()
        cfg.update(updates)
        save_config(cfg)
        send_reply(message, {"type": "config_result", "ok": True, "data": cfg})
    else:
        send_error("invalid_request", "unknown config action", message.get("req_id"))


def handle_version(message: dict[str, Any]) -> None:
    """Return versions of yt-dlp, ffmpeg, and python, plus host path."""
    ytdlp_ver = "unknown"
    try:
        out = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            ytdlp_ver = out.stdout.strip()
    except Exception:
        pass

    ffmpeg_ver = "unknown"
    try:
        out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout:
            ffmpeg_ver = out.stdout.splitlines()[0]
    except Exception:
        pass

    py_ver = sys.version.split()[0]
    host_path = os.path.abspath(__file__)

    send_reply(message, {
        "type": "version_result",
        "ok": True,
        "data": {
            "ytdlp_version": ytdlp_ver,
            "ffmpeg_version": ffmpeg_ver,
            "python_version": py_ver,
            "host_path": host_path,
            "host_name": HOST_NAME,
            "update_command": "sudo pacman -Syu yt-dlp  (or: yt-dlp -U)",
        },
    })


# ---------------------------------------------------------------------- #
# Main loop
# ---------------------------------------------------------------------- #
HANDLERS = {
    "ping": lambda m, grp=None: handle_ping(m),
    "media_info": lambda m, grp=None: handle_media_info(m),
    "metadata": lambda m, grp=None: handle_metadata(m),
    "formats": lambda m, grp=None: handle_formats(m),
    "download": handle_download,
    "cancel": handle_cancel,
    "list": handle_list,
    "config": lambda m, grp=None: handle_config(m),
    "version": lambda m, grp=None: handle_version(m),
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
        req_id = message.get("req_id")
        handler = HANDLERS.get(msg_type)
        if handler is None:
            send_error("unknown_type", f"unknown message type: {msg_type!r}", req_id)
            continue

        try:
            if msg_type in ("download", "cancel", "list"):
                handler(message, manager)
            else:
                handler(message)
        except Exception as exc:  # noqa: BLE001
            log.exception("handler error for %s", msg_type)
            send_error("internal_error", str(exc), req_id)

    log.info("Native messaging host %s shutting down", HOST_NAME)


if __name__ == "__main__":
    main()
