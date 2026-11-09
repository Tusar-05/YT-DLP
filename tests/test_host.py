"""Unit tests for host.py message routing and handler responses."""

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "native-host")
from host import (
    handle_cancel,
    handle_config,
    handle_download,
    handle_ping,
    handle_version,
)


class TestHostHandlers(unittest.TestCase):
    def test_handle_ping_preserves_req_id(self):
        sent = []
        with patch("host.send_message", side_effect=sent.append):
            handle_ping({"type": "ping", "req_id": "req-ping-99"})

        self.assertEqual(len(sent), 1)
        res = sent[0]
        self.assertEqual(res["type"], "pong")
        self.assertTrue(res["ok"])
        self.assertEqual(res["req_id"], "req-ping-99")

    def test_handle_version_returns_tools_and_req_id(self):
        sent = []
        with patch("host.send_message", side_effect=sent.append):
            handle_version({"type": "version", "req_id": "req-ver-42"})

        self.assertEqual(len(sent), 1)
        res = sent[0]
        self.assertEqual(res["type"], "version_result")
        self.assertTrue(res["ok"])
        self.assertEqual(res["req_id"], "req-ver-42")
        self.assertIn("ytdlp_version", res["data"])
        self.assertIn("ffmpeg_version", res["data"])
        self.assertIn("host_name", res["data"])

    def test_handle_config_get_and_set(self):
        sent = []
        with patch("host.send_message", side_effect=sent.append), \
             patch("host.load_config", return_value={"download_dir": "/tmp/test"}), \
             patch("host.save_config"):
            handle_config({"type": "config", "action": "get", "req_id": "cfg-1"})
            self.assertEqual(sent[-1]["data"]["download_dir"], "/tmp/test")
            self.assertEqual(sent[-1]["req_id"], "cfg-1")

            handle_config({
                "type": "config",
                "action": "set",
                "config": {"default_video_container": "webm"},
                "req_id": "cfg-2",
            })
            self.assertEqual(sent[-1]["type"], "config_result")
            self.assertEqual(sent[-1]["req_id"], "cfg-2")

    def test_handle_download_starts_and_reports_ok(self):
        sent = []
        mock_mgr = MagicMock()
        mock_mgr.start_download.return_value = "fake-uuid-1234"

        with patch("host.send_message", side_effect=sent.append):
            handle_download(
                {"type": "download", "url": "https://example.com/v", "req_id": "dl-1"},
                mock_mgr,
            )

        self.assertEqual(len(sent), 1)
        res = sent[0]
        self.assertEqual(res["type"], "download_started")
        self.assertTrue(res["ok"])
        self.assertEqual(res["download_id"], "fake-uuid-1234")
        self.assertEqual(res["req_id"], "dl-1")

    def test_handle_cancel(self):
        sent = []
        mock_mgr = MagicMock()
        mock_mgr.cancel_download.return_value = True

        with patch("host.send_message", side_effect=sent.append):
            handle_cancel(
                {"type": "cancel", "download_id": "fake-uuid", "req_id": "can-1"},
                mock_mgr,
            )

        self.assertEqual(len(sent), 1)
        res = sent[0]
        self.assertEqual(res["type"], "cancel_result")
        self.assertTrue(res["ok"])
        self.assertEqual(res["download_id"], "fake-uuid")
        self.assertEqual(res["req_id"], "can-1")


if __name__ == "__main__":
    unittest.main()
