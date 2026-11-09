"""Format discovery and metadata extraction for yt-dlp URLs.

Queries yt-dlp JSON output to enumerate available video/audio formats and metadata
for a given URL, returning structured records that the extension can render in its
format/resolution/codec selectors.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

# Cache to avoid running `yt-dlp --dump-json` multiple times for the same URL
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def is_video_url(url: str) -> bool:
    """Validate that the URL is a safe http(s) URL."""
    if not isinstance(url, str):
        return False
    url_trimmed = url.strip()
    return url_trimmed.startswith("http://") or url_trimmed.startswith("https://")


def normalize_codec_name(vcodec: str | None) -> str:
    """Normalize raw yt-dlp codec string to a user-friendly family name."""
    if not vcodec or vcodec == "none":
        return "none"
    v = vcodec.lower()
    if "av01" in v or "av1" in v:
        return "AV1"
    if "vp9" in v or "vp09" in v:
        return "VP9"
    if "avc" in v or "h264" in v or "h.264" in v:
        return "H.264"
    if "hev" in v or "h265" in v or "h.265" in v:
        return "H.265/HEVC"
    return vcodec.split(".")[0].upper()


def _run_yt_dlp_json(url: str, extra_args: list[str] | None = None) -> dict[str, Any]:
    """Run yt-dlp --dump-json and return the parsed info dict.

    Raises RuntimeError with a human-readable message on failure.
    """
    args = [
        "yt-dlp",
        "--dump-json",
        "--no-warnings",
        "--no-colors",
        "--no-exec",
        "--no-exec-before-download",
    ]
    if extra_args:
        args.extend(extra_args)
    else:
        args.append("--no-playlist")

    # Safety: use '--' so URLs starting with '-' cannot be parsed as flags
    args.append("--")
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

    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError("yt-dlp returned empty output")

    # If playlist was requested, stdout can have multiple JSON lines (one per video).
    # We parse the first line or load as single dict.
    first_line = stdout.splitlines()[0]
    try:
        return json.loads(first_line)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"yt-dlp returned invalid JSON: {exc}")


def _format_record(fmt: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single yt-dlp format dict into a stable record."""
    vcodec = fmt.get("vcodec") or "none"
    acodec = fmt.get("acodec") or "none"
    return {
        "format_id": fmt.get("format_id"),
        "ext": fmt.get("ext"),
        "resolution": fmt.get("resolution") or ("audio" if vcodec == "none" else "unknown"),
        "fps": fmt.get("fps"),
        "vcodec": vcodec,
        "codec_family": normalize_codec_name(vcodec),
        "acodec": acodec,
        "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
        "note": fmt.get("format_note") or "",
        "height": fmt.get("height"),
        "width": fmt.get("width"),
        "tbr": fmt.get("tbr"),      # total bitrate (kbps)
        "abr": fmt.get("abr"),      # audio bitrate (kbps)
        "vbr": fmt.get("vbr"),      # video bitrate (kbps)
    }


def get_media_info(url: str) -> dict[str, Any]:
    """Extract full media metadata and available formats in a single yt-dlp call."""
    info = _run_yt_dlp_json(url)

    raw_formats = info.get("formats") or []
    records = [_format_record(f) for f in raw_formats if isinstance(f, dict)]

    # Collect available video codecs (e.g. H.264, VP9, AV1)
    codecs_set: set[str] = set()
    for r in records:
        family = r.get("codec_family")
        if family and family != "none":
            codecs_set.add(family)

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

    metadata = {
        "title": info.get("title") or "Unknown title",
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail") or "",
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "webpage_url": info.get("webpage_url") or url,
        "extractor": info.get("extractor"),
        "is_playlist": info.get("_type") == "playlist" or "playlist" in url.lower(),
        "playlist_count": info.get("playlist_count"),
        "formats": {
            "video": video,
            "audio": audio,
            "codecs": sorted(codecs_set),
        },
    }
    return metadata


def discover_formats(url: str) -> dict[str, Any]:
    """Backwards-compatible wrapper returning video & audio format lists."""
    info = get_media_info(url)
    return {
        "video": info["formats"]["video"],
        "audio": info["formats"]["audio"],
        "codecs": info["formats"]["codecs"],
        "title": info["title"],
    }
