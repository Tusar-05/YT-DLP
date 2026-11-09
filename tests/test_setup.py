"""Unit tests for setup script, packaging, and deterministic ID calculation."""

import hashlib
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSetup(unittest.TestCase):
    def test_deterministic_extension_id_format(self):
        """Verify the Chrome unpacked extension ID calculation algorithm."""
        path = os.path.join(REPO_ROOT, "extension")
        h = hashlib.sha256(path.encode("utf-8")).digest()[:16]
        ext_id = "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0x0F)) for b in h)

        self.assertEqual(len(ext_id), 32)
        self.assertTrue(all("a" <= c <= "p" for c in ext_id))

    def test_setup_scripts_exist_and_executable(self):
        setup_sh = os.path.join(REPO_ROOT, "setup.sh")
        package_sh = os.path.join(REPO_ROOT, "scripts", "package.sh")

        self.assertTrue(os.path.isfile(setup_sh))
        self.assertTrue(os.access(setup_sh, os.X_OK))

        self.assertTrue(os.path.isfile(package_sh))
        self.assertTrue(os.access(package_sh, os.X_OK))

    def test_setup_script_help_flag(self):
        res = subprocess.run(
            ["bash", os.path.join(REPO_ROOT, "setup.sh"), "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage: ./setup.sh", res.stdout)
        self.assertIn("--doctor", res.stdout)


if __name__ == "__main__":
    unittest.main()
