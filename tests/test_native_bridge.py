import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from edge_model_deploy import WhisperTranscriber


class NativeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.executable = Path(self.directory.name) / "edge-transcribe"
        self.executable.touch()
        self.transcriber = WhisperTranscriber(self.executable)
        self.addCleanup(self.directory.cleanup)

    def test_failure_does_not_return_a_transcript(self):
        with patch("edge_model_deploy.native.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, "", "bad model")
            with self.assertRaisesRegex(RuntimeError, "bad model"):
                self.transcriber.transcribe("model.bin", "audio.wav")

    def test_invalid_success_output_is_rejected(self):
        for payload in ["not json", "[]", '{"text":"hello"}']:
            with self.subTest(payload=payload):
                with patch("edge_model_deploy.native.subprocess.run") as run:
                    run.return_value = subprocess.CompletedProcess([], 0, payload, "")
                    with self.assertRaises(ValueError):
                        self.transcriber.transcribe("model.bin", "audio.wav")

    def test_timestamps_are_kept_without_text_cleanup(self):
        native = {"text": "Um, a real result.", "segments": [
            {"text": "Um, a real result.", "start_ms": 530, "end_ms": 1760}]}
        with patch("edge_model_deploy.native.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, json.dumps(native), "")
            self.assertEqual(self.transcriber.transcribe("model.bin", "audio.wav"), native)

    def test_timeout_and_invalid_threads_do_not_fall_back(self):
        with self.assertRaises(ValueError):
            self.transcriber.transcribe("model.bin", "audio.wav", threads=0)
        with patch("edge_model_deploy.native.subprocess.run", side_effect=subprocess.TimeoutExpired([], 1)):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.transcriber.transcribe("model.bin", "audio.wav", timeout=1)

    def test_nonfinite_timeout_is_rejected_before_launch(self):
        for timeout in [float("nan"), float("inf"), -1.0]:
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    self.transcriber.transcribe("model.bin", "audio.wav", timeout=timeout)
