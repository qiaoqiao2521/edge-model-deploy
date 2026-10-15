"""Subprocess bridge to the real, separately built C++ Whisper backend."""

import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Union


class WhisperTranscriber:
    """Run edge-transcribe on a 16 kHz mono PCM16 WAV, without a mock fallback."""

    def __init__(self, executable: Union[str, Path]):
        self.executable = Path(executable).expanduser().resolve()
        if not self.executable.is_file():
            raise FileNotFoundError("Build edge-transcribe with CMake first: {}".format(self.executable))

    def transcribe(
        self, model_path: Union[str, Path], audio_path: Union[str, Path],
        language: str = "zh", threads: int = 4, prompt: str = "", timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """Return native segment timestamps and measurements; propagate failures."""
        if isinstance(threads, bool) or not isinstance(threads, int) or threads <= 0:
            raise ValueError("threads must be a positive integer")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        argv = [str(self.executable), "--model", str(Path(model_path).resolve()),
                "--audio", str(Path(audio_path).resolve()), "--language", language,
                "--threads", str(threads)]
        if prompt:
            argv.extend(["--prompt", prompt])
        completed = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                   check=False, timeout=timeout)
        if completed.returncode:
            raise RuntimeError("Native transcription failed (exit {}): {}".format(
                completed.returncode, completed.stderr.strip()))
        result = json.loads(completed.stdout)
        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise ValueError("Native backend returned an invalid transcription object")
        if not isinstance(result.get("segments"), list):
            raise ValueError("Native backend returned no segment list")
        return result
