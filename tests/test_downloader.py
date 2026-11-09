"""Unit tests for downloader argument construction, progress parsing, and sanitization."""

import os
import sys
import unittest

sys.path.insert(0, "native-host")
from downloader import (
    FILEPATH_PREFIX,
    PROGRESS_PREFIX,
    TITLE_PREFIX,
    DownloadManager,
    DownloadRecord,
    sanitize_download_dir,
)


class TestDownloader(unittest.TestCase):
    def test_parse_progress_normal(self):
        line = f"{PROGRESS_PREFIX}45.5%\t2.3MiB/s\t00:15"
        parsed = DownloadManager._parse_progress_line(line)
        self.assertIsNotNone(parsed)
        kind, val = parsed
        self.assertEqual(kind, "progress")
        self.assertEqual(val["percent"], 45.5)
        self.assertEqual(val["speed_str"], "2.3MiB/s")
        self.assertEqual(val["eta_str"], "00:15")

    def test_parse_progress_with_ansi(self):
        line = f"{PROGRESS_PREFIX}\x1b[0;94m 89.2%\x1b[0m\t\x1b[0;32m1.2MiB/s\x1b[0m\t00:03"
        parsed = DownloadManager._parse_progress_line(line)
        self.assertIsNotNone(parsed)
        kind, val = parsed
        self.assertEqual(kind, "progress")
        self.assertEqual(val["percent"], 89.2)
        self.assertEqual(val["speed_str"], "1.2MiB/s")

    def test_parse_filepath(self):
        line = f"{FILEPATH_PREFIX}/home/user/Videos/Downloads/sample.mp4"
        parsed = DownloadManager._parse_progress_line(line)
        self.assertIsNotNone(parsed)
        kind, val = parsed
        self.assertEqual(kind, "filepath")
        self.assertEqual(val, "/home/user/Videos/Downloads/sample.mp4")

    def test_parse_title_json(self):
        line = f'{TITLE_PREFIX}"My Awesome Video - 2026"'
        parsed = DownloadManager._parse_progress_line(line)
        self.assertIsNotNone(parsed)
        kind, val = parsed
        self.assertEqual(kind, "title")
        self.assertEqual(val, "My Awesome Video - 2026")

    def test_sanitize_download_dir_blocks_system_dirs(self):
        with self.assertRaises(ValueError):
            sanitize_download_dir("/etc")
        with self.assertRaises(ValueError):
            sanitize_download_dir("/usr/local")
        with self.assertRaises(ValueError):
            sanitize_download_dir("/root")

    def test_build_args_audio_mode(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-1", "https://example.com/audio", {})
        params = {
            "mode": "audio",
            "audio_format": "flac",
            "audio_quality": "0",
        }
        args = mgr._build_args(record, "audio", "/tmp/dl", params)

        self.assertIn("-f", args)
        self.assertIn("ba/b", args)
        self.assertIn("-x", args)
        self.assertIn("--audio-format", args)
        self.assertIn("flac", args)
        self.assertIn("--no-colors", args)
        self.assertEqual(args[-2], "--")
        self.assertEqual(args[-1], "https://example.com/audio")

    def test_build_args_video_mode_with_codec(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-2", "https://example.com/video", {})
        params = {
            "mode": "video",
            "quality": "1080",
            "codec": "AV1",
            "container": "mp4",
        }
        args = mgr._build_args(record, "video", "/tmp/dl", params)

        self.assertIn("--merge-output-format", args)
        self.assertIn("mp4", args)
        # Check AV1 format spec
        format_idx = args.index("--format")
        format_spec = args[format_idx + 1]
        self.assertIn("av01", format_spec)
        self.assertIn("height<=1080", format_spec)
        self.assertEqual(args[-2], "--")
        self.assertEqual(args[-1], "https://example.com/video")


if __name__ == "__main__":
    unittest.main()
