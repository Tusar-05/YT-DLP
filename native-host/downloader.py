"""Download management for the yt-dlp Extension Native Messaging host.

Spawns and tracks yt-dlp subprocesses, streams progress back to the extension,
and supports cancellation. All yt-dlp invocations use subprocess argument
arrays (shell=False) to avoid arbitrary command execution.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import uuid
from typing import Any, Callable, Optional

from config import ensure_download_dir, load_config
from formats import discover_formats

PROGRESS_PREFIX = "YTDL_PROGRESS\t"
FILEPATH_PREFIX = "YTDL_FILEPATH\t"
TITLE_PREFIX = "YTDL_TITLE\t"


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
        self.title: Optional[str] = None
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
        }


class DownloadManager:
    """Thread-safe manager of concurrent yt-dlp downloads."""

    def __init__(self, send_message: Callable[[dict[str, Any]], None]):
        self._send = send_message
        self._lock = threading.Lock()
        self._downloads: dict[str, DownloadRecord] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def start_download(self, params: dict[str, Any]) -> str:
        """Validate params, spawn a yt-dlp download thread, return download_id."""
        url = params.get("url", "")
        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("Invalid or missing URL")

        download_id = str(uuid.uuid4())
        record = DownloadRecord(download_id, url, params)

        mode = params.get("mode", "video")
        download_dir = params.get("download_dir") or load_config()["download_dir"]
        download_dir = ensure_download_dir(download_dir)

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
        """Request cancellation of an in-flight download. Returns True if found."""
        with self._lock:
            record = self._downloads.get(download_id)
        if record is None:
            return False
        record._cancelled.set()
        proc = record._process
        if proc is not None and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGTERM)
            except ProcessLookupError:
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

            # Build the yt-dlp argument array.
            args = self._build_args(record, mode, download_dir, params)

            record._process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            stdout = record._process.stdout
            if stdout is None:
                raise RuntimeError("yt-dlp produced no stdout")

            filepath: Optional[str] = None
            title: Optional[str] = None

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

            record._process.wait()
            stderr = record._process.stderr.read() if record._process.stderr else ""

            if record._cancelled.is_set():
                self._set_status(record, "cancelled")
                self._send({"type": "download_failed", "download_id": record.download_id, "error": "cancelled"})
                return

            if record._process.returncode != 0:
                detail = stderr.strip() or f"yt-dlp exited with code {record._process.returncode}"
                self._set_status(record, "failed", error=detail)
                self._send({"type": "download_failed", "download_id": record.download_id, "error": detail})
                return

            self._set_status(record, "completed", filepath=filepath, title=title)
            self._send({
                "type": "download_complete",
                "download_id": record.download_id,
                "filepath": filepath,
                "title": title,
            })

        except Exception as exc:  # noqa: BLE001 - report any failure to extension
            self._set_status(record, "failed", error=str(exc))
            self._send({"type": "download_failed", "download_id": record.download_id, "error": str(exc)})
        finally:
            record._process = None

    def _build_args(
        self,
        record: DownloadRecord,
        mode: str,
        download_dir: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Construct the yt-dlp argv array (never a shell string)."""
        url = record.url
        output_template = os.path.join(download_dir, "%(title)s.%(ext)s")

        args: list[str] = [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "--no-exec",
            "--no-exec-before-download",
            "--progress",
            "--newline",
            # Emit progress as tab-separated fields we can parse reliably.
            "--progress-template",
            f"{PROGRESS_PREFIX}%(progress._percent_str)s\t%(progress._speed_str)s\t%(progress._eta_str)s",
            "--print",
            f"{FILEPATH_PREFIX}%(filename)s",
            "--print",
            f"{TITLE_PREFIX}%(title)j",
            "--output",
            output_template,
        ]

        if mode == "audio":
            audio_format = params.get("audio_format") or load_config()["default_audio_format"]
            audio_quality = params.get("audio_quality") or load_config()["default_audio_quality"]
            args.extend(["-x", "--audio-format", str(audio_format), "--audio-quality", str(audio_quality)])
        else:
            # Video: prefer the requested format_id, fall back to best.
            format_id = params.get("format_id") or "best"
            args.extend(["--format", str(format_id)])
            container = params.get("container") or load_config()["default_video_container"]
            args.extend(["--merge-output-format", str(container)])

        if params.get("subtitles"):
            args.extend(["--write-subs", "--sub-langs", "all"])

        if params.get("thumbnail"):
            args.append("--write-thumbnail")

        args.append(url)
        return args

    @staticmethod
    def _parse_progress_line(line: str) -> Optional[tuple[str, Any]]:
        """Parse a yt-dlp stdout line into (kind, value)."""
        if line.startswith(PROGRESS_PREFIX):
            payload = line[len(PROGRESS_PREFIX):].strip()
            parts = payload.split("\t")
            if len(parts) >= 3:
                try:
                    percent = float(parts[0].replace("%", "").strip() or 0)
                except ValueError:
                    percent = 0.0
                return ("progress", {
                    "percent": percent,
                    "speed_str": parts[1],
                    "eta_str": parts[2],
                })
            return ("progress", {"percent": 0.0, "speed_str": "", "eta_str": ""})

        if line.startswith(FILEPATH_PREFIX):
            return ("filepath", line[len(FILEPATH_PREFIX):].strip())

        if line.startswith(TITLE_PREFIX):
            # Title is JSON-encoded (%(title)j); decode it.
            raw = line[len(TITLE_PREFIX):].strip()
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
            "downloaded_bytes": record.downloaded_bytes,
            "total_bytes": record.total_bytes,
        })
