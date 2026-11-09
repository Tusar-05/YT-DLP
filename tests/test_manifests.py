"""Unit tests for browser extension manifests and native host templates."""

import json
import os
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestManifests(unittest.TestCase):
    def test_chrome_host_manifest_template(self):
        path = os.path.join(REPO_ROOT, "native-host", "native-host-manifest.json")
        self.assertTrue(os.path.exists(path), f"Missing {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["name"], "com.yt_dlp_extension.host")
        self.assertEqual(data["type"], "stdio")
        self.assertIn("allowed_origins", data)
        self.assertIsInstance(data["allowed_origins"], list)

    def test_firefox_host_manifest_template(self):
        path = os.path.join(REPO_ROOT, "native-host", "firefox-host-manifest.json")
        self.assertTrue(os.path.exists(path), f"Missing {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["name"], "com.yt_dlp_extension.host")
        self.assertEqual(data["type"], "stdio")
        self.assertIn("allowed_extensions", data)
        self.assertIsInstance(data["allowed_extensions"], list)
        self.assertIn("ytdlp-extension@local", data["allowed_extensions"])

    def test_chrome_host_name_syntax_compliance(self):
        """Chrome enforces: only lowercase alphanumeric, underscores, dots; no hyphens."""
        import re
        pattern = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")
        path = os.path.join(REPO_ROOT, "native-host", "native-host-manifest.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertRegex(data["name"], pattern)
        self.assertNotIn("-", data["name"], "Chrome rejects hyphens in native messaging host names")

    def test_extension_manifest_gecko_id_matches_firefox_host(self):
        ext_manifest_path = os.path.join(REPO_ROOT, "extension", "manifest.json")
        self.assertTrue(os.path.exists(ext_manifest_path))
        with open(ext_manifest_path, "r", encoding="utf-8") as f:
            ext_data = json.load(f)

        self.assertEqual(ext_data["manifest_version"], 3)
        self.assertIn("browser_specific_settings", ext_data)
        gecko_id = ext_data["browser_specific_settings"]["gecko"]["id"]

        ff_host_path = os.path.join(REPO_ROOT, "native-host", "firefox-host-manifest.json")
        with open(ff_host_path, "r", encoding="utf-8") as f:
            ff_data = json.load(f)

        self.assertIn(gecko_id, ff_data["allowed_extensions"])


if __name__ == "__main__":
    unittest.main()
