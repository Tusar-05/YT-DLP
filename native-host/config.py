"""Configuration management for the yt-dlp Extension Native Messaging host.

Handles loading/saving user config (download directory, default quality/format)
and provides default constants used across the host.
"""

from __future__ import annotations

import json
import os
from typing import Any

# Default download directory per plan.md section 9.
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Videos/Downloads")

# Config lives under ~/.config/yt-dlp-extension/config.json
CONFIG_DIR = os.path.expanduser("~/.config/yt-dlp-extension")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS: dict[str, Any] = {
    "download_dir": DEFAULT_DOWNLOAD_DIR,
    "default_video_container": "mp4",
    "default_video_quality": "best",
    "default_audio_format": "mp3",
    "default_audio_quality": "192",
    "download_subtitles": False,
    "download_thumbnail": False,
    "subtitle_langs": "en",
    "rate_limit": "",
    "cookies_from_browser": "",
}


def ensure_config_dir() -> str:
    """Ensure the config directory exists and return its path."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    return CONFIG_DIR


def load_config() -> dict[str, Any]:
    """Load user config, merging over defaults. Returns a fresh dict."""
    cfg = dict(DEFAULTS)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                user = json.load(fh)
            if isinstance(user, dict):
                cfg.update(user)
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable config -> fall back to defaults silently.
            pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Atomically persist config to disk."""
    ensure_config_dir()
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, CONFIG_PATH)


def ensure_download_dir(path: str | None = None) -> str:
    """Create the download directory if needed and return its absolute path."""
    target = os.path.abspath(os.path.expanduser(path or DEFAULTS["download_dir"]))
    os.makedirs(target, exist_ok=True)
    return target
