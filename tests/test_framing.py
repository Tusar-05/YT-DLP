"""Unit tests for Native Messaging binary protocol framing."""

import io
import json
import struct
import sys
import unittest

sys.path.insert(0, "native-host")
from host import read_message, send_message


class TestFraming(unittest.TestCase):
    def test_send_message_framing(self):
        msg = {"type": "pong", "ok": True, "req_id": "test-1"}
        buf = io.BytesIO()

        send_message(msg, stream=buf)

        raw = buf.getvalue()
        self.assertGreaterEqual(len(raw), 4)

        length = struct.unpack("<I", raw[:4])[0]
        payload = json.loads(raw[4 : 4 + length].decode("utf-8"))
        self.assertEqual(payload, msg)

    def test_read_message_success(self):
        msg = {"type": "ping", "req_id": "ping-123"}
        payload = json.dumps(msg).encode("utf-8")
        data = struct.pack("<I", len(payload)) + payload

        fake_stdin = io.BytesIO(data)
        received = read_message(stream=fake_stdin)
        self.assertEqual(received, msg)

    def test_read_message_eof(self):
        fake_stdin = io.BytesIO(b"")
        self.assertIsNone(read_message(stream=fake_stdin))

    def test_read_message_partial_header(self):
        fake_stdin = io.BytesIO(b"\x01\x00")
        self.assertIsNone(read_message(stream=fake_stdin))

    def test_read_message_oversized(self):
        # 15 MB length header
        fake_stdin = io.BytesIO(struct.pack("<I", 15 * 1024 * 1024))
        self.assertIsNone(read_message(stream=fake_stdin))

    def test_read_message_malformed_json(self):
        payload = b"this is not json"
        data = struct.pack("<I", len(payload)) + payload
        fake_stdin = io.BytesIO(data)
        self.assertIsNone(read_message(stream=fake_stdin))


if __name__ == "__main__":
    unittest.main()
