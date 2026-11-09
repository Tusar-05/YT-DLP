"""Format discovery for yt-dlp URLs.

Queries yt-dlp JSON output to enumerate available video/audio formats for a
given URL, returning structured format records the extension can render in its
format/resolution selectors.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


def _run_yt_dlp_json(url: str, extra_args: list[str] | None = None) -> dict[str, Any]:
    """Run yt-dlp --dump-json and return the parsed info dict.

    Raises RuntimeError with a human-readable message on failure.
    """
    args = [
        "yt-dlp",
        "--no-playlist",
        "--dump-json",
        "--no-warnings",
        "--no-exec",
        "--no-exec-before-download",
    ]
    if extra_args:
        args.extend(extra_args)
    args.append(url)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError("yt-dlp is not installed or not on PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("yt-dlp timed out while extracting metadata")

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"yt-dlp failed: {detail}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlp returned invalid JSON: {exc}")


def _format_record(fmt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single yt-dlp format dict into a stable record."""
    return {
        "format_id": fmt.get("format_id"),
        "ext": fmt.get("ext"),
        "resolution": fmt.get("resolution") or "audio",
        "fps": fmt.get("fps"),
        "vcodec": fmt.get("vcodec") or "none",
        "acodec": fmt.get("acodec") or "none",
        "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
        "note": fmt.get("format_note") or "",
        "height": fmt.get("height"),
        "width": fmt.get("width"),
        "tbr": fmt.get("tbr"),      # total bitrate (kbps)
        "abr": fmt.get("abr"),      # audio bitrate (kbps)
        "vbr": fmt.get("vbr"),      # video bitrate (kbps)
    }


def discover_formats(url: str) -> list[dict[str, Any]]:
    """Return available formats for *url*, split into video and audio groups.

    Each record includes format_id, ext, resolution, codecs, bitrates, filesize
    and a human-readable note. Video-only formats (acodec == none) and
    audio-only formats (vcodec == none) are both included so the extension can
    present the appropriate selector per mode.
    """
    info = _run_yt_dlp_json(url)
    raw_formats = info.get("formats") or []
    records = [_format_record(f) for f in raw_formats if isinstance(f, dict)]

    # Sort video formats by height descending, then audio by bitrate descending.
    video = sorted(
        [r for r in records if r["vcodec"] != "none"],
        key=lambda r: (r["height"] or 0, r["tbr"] or 0),
        reverse=True,
    )
    audio = sorted(
        [r for r in records if r["acodec"] != "none"],
        key=lambda r: (r["abr"] or 0, r["tbr"] or 0),
        reverse=True,
    )

    return {"video": video, "audio": audio, "title": info.get("title", "")}


def is_video_url(url: str) -> bool:
    """Quick sanity check that the URL looks like an http(s) media page."""
    return url.startswith("http://") or url.startswith("https://")
