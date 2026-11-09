"""Download management for the yt-dlp Extension Native Messaging host.

Spawns and tracks yt-dlp subprocesses, streams progress back to the extension,
and supports cancellation. All yt-dlp invocations use subprocess argument
arrays (shell=False) to avoid arbitrary command execution.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
import uuid
from typing import Any, Callable, Optional

from config import ensure_download_dir, load_config

PROGRESS_PREFIX = "YTDL_PROGRESS\t"
FILEPATH_PREFIX = "YTDL_FILEPATH\t"
TITLE_PREFIX = "YTDL_TITLE\t"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Disallowed directories for safety
BLOCKED_DIRS = {"/etc", "/bin", "/sbin", "/usr", "/boot", "/sys", "/proc", "/dev", "/root"}


def sanitize_download_dir(dir_path: str | None) -> str:
    """Validate and sanitize target download directory."""
    raw = dir_path or load_config().get("download_dir") or "~/Videos/Downloads"
    expanded = os.path.abspath(os.path.expanduser(raw))
    for blocked in BLOCKED_DIRS:
        if expanded == blocked or expanded.startswith(blocked + "/"):
            raise ValueError(f"Downloading into system directory {blocked} is disallowed")
    return ensure_download_dir(expanded)


class DownloadRecord:
    """Mutable status record for a single download."""

    def __init__(self, download_id: str, url: str, params: dict[str, Any]):
        self.download_id = download_id
        self.url = url
        self.params = params
        self.status: str = "starting"  # starting | running | completed | failed | cancelled
        self.percent: float = 0.0
        self.speed_str: str = ""
        self.eta_str: str = ""
        self.downloaded_bytes: int = 0
        self.total_bytes: int | None = None
        self.filepath: Optional[str] = None
        self.title: Optional[str] = params.get("title")
        self.error: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._cancelled = threading.Event()

    def to_dict(self) -> dict[str, Any]:
        return {
            "download_id": self.download_id,
            "url": self.url,
            "status": self.status,
            "percent": self.percent,
            "speed_str": self.speed_str,
            "eta_str": self.eta_str,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "filepath": self.filepath,
            "title": self.title,
            "error": self.error,
            "mode": self.params.get("mode", "video"),
        }


class DownloadManager:
    """Thread-safe manager of concurrent yt-dlp downloads."""

    def __init__(self, send_message: Callable[[dict[str, Any]], None]):
        self._send = send_message
        self._lock = threading.Lock()
        self._downloads: dict[str, DownloadRecord] = {}

    def start_download(self, params: dict[str, Any]) -> str:
        """Validate params, spawn a yt-dlp download thread, return download_id."""
        url = params.get("url", "")
        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Invalid or missing URL")

        download_id = str(uuid.uuid4())
        record = DownloadRecord(download_id, url, params)

        mode = params.get("mode", "video")
        download_dir = sanitize_download_dir(params.get("download_dir"))

        thread = threading.Thread(
            target=self._run_download,
            args=(record, mode, download_dir, params),
            daemon=True,
        )

        with self._lock:
            self._downloads[download_id] = record

        record._thread = thread
        thread.start()
        return download_id

    def cancel_download(self, download_id: str) -> bool:
        """Request cancellation of an in-flight download."""
        with self._lock:
            record = self._downloads.get(download_id)
        if record is None:
            return False
        record._cancelled.set()
        proc = record._process
        if proc is not None and proc.poll() is None:
            try:
                # Terminate the process group to ensure ffmpeg and sub-processes are killed
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                try:
                    proc.terminate()
                except Exception:
                    pass
        return True

    def get_record(self, download_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            record = self._downloads.get(download_id)
        return record.to_dict() if record else None

    def list_downloads(self, filter_: str = "all") -> list[dict[str, Any]]:
        with self._lock:
            records = list(self._downloads.values())
        if filter_ == "all":
            return [r.to_dict() for r in records]
        if filter_ == "active":
            return [r.to_dict() for r in records if r.status in ("starting", "running")]
        return [r.to_dict() for r in records if r.status == filter_]

    # ------------------------------------------------------------------ #
    # Internal: yt-dlp execution
    # ------------------------------------------------------------------ #
    def _run_download(
        self,
        record: DownloadRecord,
        mode: str,
        download_dir: str,
        params: dict[str, Any],
    ) -> None:
        try:
            self._set_status(record, "running")

            args = self._build_args(record, mode, download_dir, params)

            # Start process in a new process group so child processes (like ffmpeg) can be killed
            record._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

            stdout = record._process.stdout
            if stdout is None:
                raise RuntimeError("yt-dlp produced no stdout")

            filepath: Optional[str] = None
            title: Optional[str] = record.title

            for line in stdout:
                if record._cancelled.is_set():
                    break
                line = line.rstrip("\n")
                if not line:
                    continue
                parsed = self._parse_progress_line(line)
                if parsed is None:
                    continue
                kind, value = parsed
                if kind == "progress":
                    self._apply_progress(record, value)
                    self._notify_progress(record)
                elif kind == "filepath":
                    filepath = value
                elif kind == "title":
                    title = value
                    record.title = value

            record._process.wait()
            stderr = record._process.stderr.read() if record._process.stderr else ""

            if record._cancelled.is_set():
                self._set_status(record, "cancelled")
                self._send({
                    "type": "download_failed",
                    "download_id": record.download_id,
                    "error": "cancelled",
                    "status": "cancelled",
                })
                return

            if record._process.returncode != 0:
                detail = stderr.strip() or f"yt-dlp exited with code {record._process.returncode}"
                self._set_status(record, "failed", error=detail)
                self._send({
                    "type": "download_failed",
                    "download_id": record.download_id,
                    "error": detail,
                    "status": "failed",
                })
                return

            self._set_status(record, "completed", filepath=filepath, title=title)
            self._send({
                "type": "download_complete",
                "download_id": record.download_id,
                "filepath": filepath,
                "title": title or "Media download",
                "status": "completed",
            })

        except Exception as exc:  # noqa: BLE001
            self._set_status(record, "failed", error=str(exc))
            self._send({
                "type": "download_failed",
                "download_id": record.download_id,
                "error": str(exc),
                "status": "failed",
            })
        finally:
            record._process = None

    def _build_args(
        self,
        record: DownloadRecord,
        mode: str,
        download_dir: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Construct the yt-dlp argv array."""
        url = record.url
        is_playlist = bool(params.get("playlist"))

        if is_playlist:
            output_template = os.path.join(download_dir, "%(playlist_title,playlist)s/%(playlist_index,0)02d - %(title)s.%(ext)s")
        else:
            output_template = os.path.join(download_dir, "%(title)s.%(ext)s")

        args: list[str] = [
            "yt-dlp",
            "--no-warnings",
            "--no-colors",
            "--no-exec",
            "--no-exec-before-download",
            "--progress",
            "--newline",
            "--progress-template",
            f"{PROGRESS_PREFIX}%(progress._percent_str)s\t%(progress._speed_str)s\t%(progress._eta_str)s",
            "--print",
            f"after_move:{FILEPATH_PREFIX}%(filepath)s",
            "--print",
            f"{TITLE_PREFIX}%(title)j",
            "--output",
            output_template,
        ]

        if is_playlist:
            args.append("--yes-playlist")
        else:
            args.append("--no-playlist")

        if mode == "audio":
            audio_format = params.get("audio_format") or load_config().get("default_audio_format", "mp3")
            audio_quality = params.get("audio_quality") or load_config().get("default_audio_quality", "192")
            # CRITICAL: -f ba/b ensures yt-dlp only downloads audio stream, not 4K video!
            args.extend([
                "-f", "ba/b",
                "-x",
                "--audio-format", str(audio_format),
                "--audio-quality", str(audio_quality),
            ])
        else:
            # Video mode
            resolution = params.get("quality") or params.get("resolution") or "best"
            codec = params.get("codec")
            container = params.get("container") or load_config().get("default_video_container", "mp4")

            # Determine format string
            if params.get("format_id") and not codec:
                args.extend(["--format", str(params["format_id"])])
            else:
                h_filter = f"[height<={resolution}]" if resolution and resolution != "best" else ""
                c_filter = ""
                if codec == "H.264":
                    c_filter = "[vcodec^=avc1]"
                elif codec == "VP9":
                    c_filter = "[vcodec^=vp9]"
                elif codec == "AV1":
                    c_filter = "[vcodec^=av01]"
                elif codec == "H.265/HEVC":
                    c_filter = "[vcodec^=hev1]"

                if c_filter:
                    # Prefer requested codec, fall back to bestvideo with requested height
                    format_spec = f"bestvideo{h_filter}{c_filter}+bestaudio/bestvideo{h_filter}+bestaudio/best{h_filter}"
                else:
                    format_spec = f"bestvideo{h_filter}+bestaudio/best{h_filter}" if h_filter else "bestvideo+bestaudio/best"

                args.extend(["--format", format_spec])

            args.extend(["--merge-output-format", str(container)])

        if params.get("subtitles"):
            args.extend(["--write-subs", "--sub-langs", "all"])

        if params.get("thumbnail"):
            args.append("--write-thumbnail")

        # Safety: use '--' before URL so flags cannot be injected
        args.append("--")
        args.append(url)
        return args

    @staticmethod
    def _parse_progress_line(line: str) -> Optional[tuple[str, Any]]:
        """Parse a yt-dlp stdout line into (kind, value)."""
        # Strip ANSI escape codes
        clean_line = ANSI_ESCAPE_RE.sub("", line).strip()

        if clean_line.startswith(PROGRESS_PREFIX.strip()):
            payload = clean_line[len(PROGRESS_PREFIX.strip()):].strip()
            parts = payload.split("\t")
            if len(parts) >= 3:
                pct_str = parts[0].replace("%", "").strip()
                try:
                    percent = float(pct_str) if pct_str else 0.0
                except ValueError:
                    percent = 0.0
                return ("progress", {
                    "percent": max(0.0, min(100.0, percent)),
                    "speed_str": parts[1].strip(),
                    "eta_str": parts[2].strip(),
                })
            return ("progress", {"percent": 0.0, "speed_str": "", "eta_str": ""})

        if FILEPATH_PREFIX.strip() in clean_line:
            parts = clean_line.split(FILEPATH_PREFIX.strip(), 1)
            return ("filepath", parts[1].strip())

        if TITLE_PREFIX.strip() in clean_line:
            parts = clean_line.split(TITLE_PREFIX.strip(), 1)
            raw = parts[1].strip()
            try:
                import json as _json
                return ("title", _json.loads(raw))
            except Exception:
                return ("title", raw)

        return None

    @staticmethod
    def _apply_progress(record: DownloadRecord, value: dict[str, Any]) -> None:
        record.percent = float(value.get("percent", 0.0) or 0.0)
        record.speed_str = value.get("speed_str", "") or ""
        record.eta_str = value.get("eta_str", "") or ""

    def _set_status(
        self,
        record: DownloadRecord,
        status: str,
        filepath: Optional[str] = None,
        title: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        record.status = status
        if filepath is not None:
            record.filepath = filepath
        if title is not None:
            record.title = title
        if error is not None:
            record.error = error

    def _notify_progress(self, record: DownloadRecord) -> None:
        self._send({
            "type": "progress",
            "download_id": record.download_id,
            "percent": record.percent,
            "speed_str": record.speed_str,
            "eta_str": record.eta_str,
            "title": record.title,
            "status": record.status,
        })
