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

    def test_build_args_subtitles_and_playlist_items(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-3", "https://example.com/playlist", {})
        params = {
            "mode": "video",
            "playlist": True,
            "playlist_items": "1-3,5",
            "subtitles": True,
            "subtitle_langs": "en,es",
        }
        args = mgr._build_args(record, "video", "/tmp/dl", params)
        self.assertIn("--yes-playlist", args)
        self.assertIn("--playlist-items", args)
        self.assertIn("1-3,5", args)
        self.assertIn("--write-subs", args)
        self.assertIn("--sub-langs", args)
        self.assertIn("en,es", args)

    def test_build_args_resilience_and_rate_limit(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-4", "https://example.com/video", {})
        params = {
            "mode": "video",
            "rate_limit": "2.5M",
        }
        args = mgr._build_args(record, "video", "/tmp/dl", params)
        self.assertIn("--continue", args)
        self.assertIn("--retries", args)
        self.assertIn("3", args)
        self.assertIn("--fragment-retries", args)
        self.assertIn("--limit-rate", args)
        self.assertIn("2.5M", args)

    def test_build_args_cookies_browser_sanitization(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-5", "https://example.com/video", {})
        # Valid browser
        params_valid = {"cookies_from_browser": "firefox"}
        args_valid = mgr._build_args(record, "video", "/tmp/dl", params_valid)
        self.assertIn("--cookies-from-browser", args_valid)
        self.assertIn("firefox", args_valid)

        # Invalid/unrecognized browser should be ignored for security
        params_invalid = {"cookies_from_browser": "malicious;rm -rf"}
        args_invalid = mgr._build_args(record, "video", "/tmp/dl", params_invalid)
        self.assertNotIn("--cookies-from-browser", args_invalid)

    def test_build_args_rate_limit_edge_cases_and_zero(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-rl", "https://example.com/video", {})

        # Zero and 0M should be ignored
        for zero_val in ("0", "0M", "0k"):
            args = mgr._build_args(record, "video", "/tmp/dl", {"rate_limit": zero_val})
            self.assertNotIn("--limit-rate", args)

        # Malformed strings should be ignored
        for bad_val in ("malicious; rm -rf /", "-5M", "abc", "100.200.300M"):
            args = mgr._build_args(record, "video", "/tmp/dl", {"rate_limit": bad_val})
            self.assertNotIn("--limit-rate", args)

    def test_build_args_playlist_items_injection_blocked(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-pl", "https://example.com/playlist", {})

        # Malformed playlist_items or items without digits should be omitted
        for bad_items in ("1-5; rm -rf /", "--", "::", "---", "--exec calc"):
            args = mgr._build_args(record, "video", "/tmp/dl", {"playlist": True, "playlist_items": bad_items})
            self.assertNotIn("--playlist-items", args)

        # Valid items with digits and ranges should be accepted
        for good_items in ("1-5", "1, 3, 5-8", ":5", "10:"):
            args = mgr._build_args(record, "video", "/tmp/dl", {"playlist": True, "playlist_items": good_items})
            self.assertIn("--playlist-items", args)
            self.assertIn(good_items, args)

    def test_build_args_subtitles_injection_and_fallback(self):
        mgr = DownloadManager(lambda m: None)
        record = DownloadRecord("id-sub", "https://example.com/video", {})

        # Injection attempts starting with hyphen or containing spaces/semicolons should fall back to 'all'
        for bad_lang in ("--some-flag", "-v", "en; rm -rf", "invalid$lang"):
            args = mgr._build_args(record, "video", "/tmp/dl", {"subtitles": True, "subtitle_langs": bad_lang})
            self.assertIn("--write-subs", args)
            self.assertIn("--sub-langs", args)
            idx = args.index("--sub-langs")
            self.assertEqual(args[idx + 1], "all")

        # Empty string should fall back to default subtitle_langs ("en")
        args_empty = mgr._build_args(record, "video", "/tmp/dl", {"subtitles": True, "subtitle_langs": ""})
        idx = args_empty.index("--sub-langs")
        self.assertEqual(args_empty[idx + 1], "en")

        # Valid languages should be preserved
        for good_lang in ("en", "es", "en.*", "zh-Hans,zh-Hant", "pt_BR"):
            args = mgr._build_args(record, "video", "/tmp/dl", {"subtitles": True, "subtitle_langs": good_lang})
            idx = args.index("--sub-langs")
            self.assertEqual(args[idx + 1], good_lang)


if __name__ == "__main__":
    unittest.main()
