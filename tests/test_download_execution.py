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

    def test_manager_shutdown_cancels_active(self):
        manager = DownloadManager(send_message=lambda m: None)
        record1 = DownloadRecord("dl-active-1", "https://example.com/1", {})
        record1.status = "running"
        record2 = DownloadRecord("dl-done-2", "https://example.com/2", {})
        record2.status = "completed"

        with manager._lock:
            manager._downloads["dl-active-1"] = record1
            manager._downloads["dl-done-2"] = record2

        with patch.object(manager, "cancel_download") as mock_cancel:
            manager.shutdown()
            mock_cancel.assert_called_once_with("dl-active-1")

    def test_run_download_progress_throttled(self):
        messages = []
        manager = DownloadManager(send_message=messages.append)
        record = DownloadRecord("dl-mock-throttle", "https://example.com/test", {})

        fake_lines = [
            "YTDL_PROGRESS\t10.0%\t1.0MiB/s\t00:10\n",
            "YTDL_PROGRESS\t11.0%\t1.0MiB/s\t00:10\n",
            "YTDL_PROGRESS\t12.0%\t1.0MiB/s\t00:10\n",
            "YTDL_PROGRESS\t100.0%\t2.0MiB/s\t00:00\n",
            "after_move:YTDL_FILEPATH\t/tmp/downloads/video.mp4\n",
        ]

        mock_proc = MagicMock()
        mock_proc.stdout = fake_lines
        mock_proc.stderr = MagicMock()
        mock_proc.stderr.read.return_value = ""
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0

        times = [1000.0, 1000.05, 1000.10, 1000.15]
        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("time.time", side_effect=times):
            manager._run_download(record, "video", "/tmp/downloads", {})

        progress_msgs = [m for m in messages if m["type"] == "progress"]
        self.assertEqual(len(progress_msgs), 2)
        self.assertEqual(progress_msgs[0]["percent"], 10.0)
        self.assertEqual(progress_msgs[1]["percent"], 100.0)

    def test_cancel_download_watchdog_escalates_to_sigkill(self):
        import signal
        manager = DownloadManager(send_message=lambda m: None)
        record = DownloadRecord("dl-kill-1", "https://example.com/test", {})

        mock_proc = MagicMock()
        mock_proc.pid = 9876
        mock_proc.poll.return_value = None
        record._process = mock_proc

        with manager._lock:
            manager._downloads["dl-kill-1"] = record

        killed_signals = []
        def fake_killpg(pgid, sig):
            killed_signals.append((pgid, sig))

        with patch("os.getpgid", return_value=9876), \
             patch("os.killpg", side_effect=fake_killpg), \
             patch("time.sleep", return_value=None):
            ok = manager.cancel_download("dl-kill-1")
            self.assertTrue(ok)
            time.sleep(0.05)

        self.assertIn((9876, signal.SIGTERM), killed_signals)
        self.assertIn((9876, signal.SIGKILL), killed_signals)

    def test_run_download_large_stderr_does_not_deadlock(self):
        import sys as _sys
        manager = DownloadManager(send_message=lambda m: None)
        record = DownloadRecord("dl-stderr-1", "https://example.com/test", {})

        flood_stderr = [
            _sys.executable, "-c",
            "import sys; sys.stderr.write('E' * 200000); sys.exit(1)",
        ]

        worker = threading.Thread(
            target=manager._run_download,
            args=(record, "video", "/tmp", {}),
            daemon=True,
        )
        with patch.object(DownloadManager, "_build_args", return_value=flood_stderr):
            worker.start()
            worker.join(timeout=30)

        self.assertFalse(worker.is_alive(), "download deadlocked on a full stderr pipe")
        self.assertEqual(record.status, "failed")
        self.assertIn("E", record.error or "")

    def test_early_cancellation_before_process_spawn(self):
        messages = []
        manager = DownloadManager(send_message=messages.append)
        record = DownloadRecord("dl-early-cancel", "https://example.com/test", {})
        record._cancelled.set()

        with patch("subprocess.Popen") as mock_popen:
            manager._run_download(record, "video", "/tmp", {})
            mock_popen.assert_not_called()

        self.assertEqual(record.status, "cancelled")
        fail_msg = next(m for m in messages if m["type"] == "download_failed")
        self.assertEqual(fail_msg["status"], "cancelled")

    def test_start_download_rejects_malformed_urls(self):
        manager = DownloadManager(send_message=lambda m: None)
        invalid_urls = [
            "https://example.com\nmalicious",
            "https://example.com\rmalicious",
            "https://example.com\0malicious",
            "ftp://example.com/file.mp4",
            "file:///etc/passwd",
            "",
            12345,
        ]
        for url in invalid_urls:
            with self.assertRaises(ValueError):
                manager.start_download({"url": url})


if __name__ == "__main__":
    unittest.main()
