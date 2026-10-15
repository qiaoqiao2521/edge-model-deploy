"""Opt-in checks against the actual compiled CLI, without downloading a model."""

import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


EXECUTABLE = os.environ.get('EDGE_NATIVE_EXECUTABLE')


def chunk(tag: bytes, body: bytes) -> bytes:
    return tag + struct.pack('<I', len(body)) + body + (b'\x00' if len(body) % 2 else b'')


def wav(rate: int = 16000, channels: int = 1, extra: bytes = b'') -> bytes:
    fmt = struct.pack('<HHIIHH', 1, channels, rate, rate * channels * 2, channels * 2, 16)
    body = b'WAVE' + extra + chunk(b'fmt ', fmt) + chunk(b'data', b'\x00\x00' * 160)
    return b'RIFF' + struct.pack('<I', len(body)) + body


@unittest.skipUnless(EXECUTABLE, 'set EDGE_NATIVE_EXECUTABLE to test the built CLI')
class NativeCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def invoke(self, content: bytes, threads: str = '1'):
        audio = self.directory / 'audio.wav'
        audio.write_bytes(content)
        return subprocess.run([
            str(Path(EXECUTABLE).resolve()), '--model', str(self.directory / 'missing.bin'),
            '--audio', str(audio), '--language', 'en', '--threads', threads,
        ], capture_output=True, text=True, timeout=10)

    def test_wrong_format_and_truncation_fail_without_success_json(self):
        for content in [b'', wav(8000), wav(channels=2), wav()[:-1]]:
            with self.subTest(length=len(content)):
                result = self.invoke(content)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('Model must be a non-empty', result.stderr)

    def test_unknown_odd_chunk_reaches_real_model_loading(self):
        result = self.invoke(wav(extra=chunk(b'JUNK', b'abc')))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('Model must be a non-empty', result.stderr)

    def test_invalid_thread_count_is_rejected_before_model_loading(self):
        for threads in ['0', '-1', '513', '4junk']:
            with self.subTest(threads=threads):
                result = self.invoke(wav(), threads=threads)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('Model must be a non-empty', result.stderr)
