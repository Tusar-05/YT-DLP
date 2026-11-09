"""Unit tests for format discovery and metadata extraction."""

import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "native-host")
from formats import (
    _format_record,
    discover_formats,
    get_media_info,
    is_video_url,
    normalize_codec_name,
)


class TestFormats(unittest.TestCase):
    def test_url_validation(self):
        self.assertTrue(is_video_url("https://www.youtube.com/watch?v=12345"))
        self.assertTrue(is_video_url("http://example.com/video.mp4"))
        self.assertFalse(is_video_url("ftp://example.com/file"))
        self.assertFalse(is_video_url("file:///etc/passwd"))
        self.assertFalse(is_video_url("javascript:alert(1)"))
        self.assertFalse(is_video_url(""))
        self.assertFalse(is_video_url("https://example.com\nmalicious"))
        self.assertFalse(is_video_url("https://example.com\rmalicious"))
        self.assertFalse(is_video_url("https://example.com\0malicious"))
        self.assertFalse(is_video_url(12345))  # type: ignore

    def test_codec_normalization(self):
        self.assertEqual(normalize_codec_name("avc1.640028"), "H.264")
        self.assertEqual(normalize_codec_name("h264"), "H.264")
        self.assertEqual(normalize_codec_name("vp09.00.51.08"), "VP9")
        self.assertEqual(normalize_codec_name("vp9"), "VP9")
        self.assertEqual(normalize_codec_name("av01.0.08M.08"), "AV1")
        self.assertEqual(normalize_codec_name("hev1.1.6.L93.B0"), "H.265/HEVC")
        self.assertEqual(normalize_codec_name("none"), "none")

    def test_format_record(self):
        raw = {
            "format_id": "137",
            "ext": "mp4",
            "resolution": "1920x1080",
            "fps": 30,
            "vcodec": "avc1.640028",
            "acodec": "none",
            "filesize": 52428800,
            "height": 1080,
            "width": 1920,
            "tbr": 4500,
            "vbr": 4300,
        }
        rec = _format_record(raw)
        self.assertEqual(rec["format_id"], "137")
        self.assertEqual(rec["ext"], "mp4")
        self.assertEqual(rec["codec_family"], "H.264")
        self.assertEqual(rec["height"], 1080)
        self.assertEqual(rec["filesize"], 52428800)

    @patch("formats._run_yt_dlp_json")
    def test_get_media_info_mock(self, mock_run):
        mock_run.return_value = {
            "title": "Big Buck Bunny",
            "uploader": "Blender Foundation",
            "duration": 596,
            "thumbnail": "https://example.com/thumb.jpg",
            "formats": [
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "height": 1080,
                    "vcodec": "avc1.640028",
                    "acodec": "none",
                    "tbr": 4000,
                },
                {
                    "format_id": "248",
                    "ext": "webm",
                    "height": 1080,
                    "vcodec": "vp9",
                    "acodec": "none",
                    "tbr": 3500,
                },
                {
                    "format_id": "140",
                    "ext": "m4a",
                    "height": None,
                    "vcodec": "none",
                    "acodec": "mp4a.40.2",
                    "abr": 128,
                    "tbr": 128,
                },
            ],
        }

        info = get_media_info("https://example.com/watch?v=mock")
        self.assertEqual(info["title"], "Big Buck Bunny")
        self.assertEqual(info["channel"], "Blender Foundation")
        self.assertEqual(len(info["formats"]["video"]), 2)
        self.assertEqual(len(info["formats"]["audio"]), 1)
        self.assertIn("H.264", info["formats"]["codecs"])
        self.assertIn("VP9", info["formats"]["codecs"])

    @patch("subprocess.run")
    def test_run_yt_dlp_json_cookies_browser_sanitization(self, mock_subproc):
        from formats import _run_yt_dlp_json
        mock_res = mock_subproc.return_value
        mock_res.returncode = 0
        mock_res.stdout = '{"title": "Test Video"}\n'

        # Valid browser in config
        with patch("formats.load_config", return_value={"cookies_from_browser": "brave"}):
            _run_yt_dlp_json("https://example.com/test")
            args = mock_subproc.call_args[0][0]
            self.assertIn("--cookies-from-browser", args)
            self.assertIn("brave", args)

        # Invalid browser should be ignored
        with patch("formats.load_config", return_value={"cookies_from_browser": "bad;browser"}):
            _run_yt_dlp_json("https://example.com/test")
            args = mock_subproc.call_args[0][0]
            self.assertNotIn("--cookies-from-browser", args)


if __name__ == "__main__":
    unittest.main()
