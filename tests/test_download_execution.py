"""Tests for DownloadManager execution, progress event emission, and cancellation."""

import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "native-host")
from downloader import DownloadManager, DownloadRecord


class TestDownloadExecution(unittest.TestCase):
    def test_run_download_success(self):
        messages = []
        manager = DownloadManager(send_message=messages.append)
        record = DownloadRecord("dl-mock-1", "https://example.com/test", {})

        fake_lines = [
            "YTDL_TITLE\t\"Mock Video Title\"\n",
            "YTDL_PROGRESS\t25.0%\t1.5MiB/s\t00:10\n",
            "YTDL_PROGRESS\t75.0%\t2.0MiB/s\t00:03\n",
            "after_move:YTDL_FILEPATH\t/tmp/downloads/video.mp4\n",
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = fake_lines
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        with patch("subprocess.Popen", return_value=mock_proc):
            manager._run_download(record, "video", "/tmp/downloads", {})

        # Verify status
        self.assertEqual(record.status, "completed")
        self.assertEqual(record.title, "Mock Video Title")
        self.assertEqual(record.filepath, "/tmp/downloads/video.mp4")

        # Verify messages sent: progress updates + download_complete
        msg_types = [m["type"] for m in messages]
        self.assertIn("progress", msg_types)
        self.assertIn("download_complete", msg_types)

        complete_msg = next(m for m in messages if m["type"] == "download_complete")
        self.assertEqual(complete_msg["download_id"], "dl-mock-1")
        self.assertEqual(complete_msg["title"], "Mock Video Title")
        self.assertEqual(complete_msg["filepath"], "/tmp/downloads/video.mp4")

    def test_run_download_failure(self):
        messages = []
        manager = DownloadManager(send_message=messages.append)
        record = DownloadRecord("dl-mock-2", "https://example.com/fail", {})

        mock_proc = MagicMock()
        mock_proc.stdout = []
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = "ERROR: Video unavailable"
        mock_proc.returncode = 1
        mock_proc.wait.return_value = 1

        with patch("subprocess.Popen", return_value=mock_proc):
            manager._run_download(record, "video", "/tmp/downloads", {})

        self.assertEqual(record.status, "failed")
        self.assertIn("Video unavailable", record.error)

        msg_types = [m["type"] for m in messages]
        self.assertIn("download_failed", msg_types)

    def test_run_download_cancelled(self):
        messages = []
        manager = DownloadManager(send_message=messages.append)
        record = DownloadRecord("dl-mock-3", "https://example.com/cancel", {})
        record._cancelled.set()

        mock_proc = MagicMock()
        mock_proc.stdout = ["YTDL_PROGRESS\t10.0%\t1MiB/s\t00:20\n"]
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = -15
        mock_proc.wait.return_value = -15

        with patch("subprocess.Popen", return_value=mock_proc):
            manager._run_download(record, "video", "/tmp/downloads", {})

        self.assertEqual(record.status, "cancelled")
        fail_msg = next(m for m in messages if m["type"] == "download_failed")
        self.assertEqual(fail_msg["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
