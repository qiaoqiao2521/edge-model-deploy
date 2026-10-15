"""Protocol tests use tiny synthetic WAVs, never downloaded weights or speech."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

from scripts.benchmark import aggregate, execute_trial, load_manifest, make_schedule, normalize_words, word_errors
from scripts.prepare_librispeech import prepare, select_utterances


class WordErrorTests(unittest.TestCase):
    def test_hand_calculated_insert_delete_substitute(self) -> None:
        cases = [
            ("one two three", "one too three", (1, 0, 0)),
            ("one two three", "one three", (0, 1, 0)),
            ("one two three", "one two extra three", (0, 0, 1)),
            ("one two three", "one too three extra", (1, 0, 1)),
        ]
        for reference, hypothesis, counts in cases:
            with self.subTest(hypothesis=hypothesis):
                result = word_errors(reference, hypothesis)
                self.assertEqual(tuple(result[key] for key in ("substitutions", "deletions", "insertions")), counts)
                self.assertEqual(result["errors"], sum(counts))
                self.assertEqual(result["wer"], sum(counts) / 3)

    def test_empty_hypothesis_is_all_deletions(self) -> None:
        self.assertEqual(word_errors("one two", "")["deletions"], 2)

    def test_empty_normalized_reference_is_rejected(self) -> None:
        for text in ("", "  ", "!?'.."):
            with self.assertRaises(ValueError):
                word_errors(text, "one")

    def test_normalization_preserves_boundaries_and_handles_apostrophes(self) -> None:
        self.assertEqual(normalize_words("DON'T, re-enter/foo; John’s!  12"),
                         ["dont", "re", "enter", "foo", "johns", "12"])
        self.assertEqual(word_errors("DON'T WAIT!", "dont wait")["wer"], 0)


class ManifestAndSelectionTests(unittest.TestCase):
    def test_numeric_sampling_is_independent_of_archive_order(self) -> None:
        names = [f"LibriSpeech/test-clean/{speaker}/{chapter}/{speaker}-{chapter}-{utterance}.flac"
                 for speaker in (100, 20, 3, 2, 1) for chapter in (10, 2) for utterance in (10, 2, 1)]
        names.append("../../test-clean/0/0/0-0-0.flac")
        selected = select_utterances(list(reversed(names)))
        self.assertEqual(len(selected), 12)
        self.assertEqual([Path(name).stem for name in selected[:3]], ["1-2-1", "1-2-2", "1-2-10"])
        self.assertEqual([name.split("/")[2] for name in selected[::3]], ["1", "2", "3", "20"])

    def test_insufficient_sample_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_utterances(["LibriSpeech/test-clean/1/1/1-1-1.flac"])

    def test_archive_checksum_failure_precedes_decoding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "test-clean.tar.gz"
            archive.write_bytes(b"not the official archive")
            with self.assertRaisesRegex(ValueError, "MD5 mismatch"):
                prepare(archive, Path(directory) / "output", "missing-ffmpeg")

    def test_manifest_audio_hash_duration_and_path_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            audio = base / "clip.wav"
            write_wav(audio)
            clip = {"id": "1-2-3", "speaker": "1", "audio": "clip.wav",
                    "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
                    "duration_sec": 0.01, "reference": "ONE TWO"}
            manifest_path = base / "manifest.json"
            def save() -> None:
                manifest_path.write_text(json.dumps({"schema_version": 1, "clips": [clip]}))
            save()
            _, loaded = load_manifest(manifest_path)
            self.assertEqual(loaded[0]["audio_path"], str(audio))
            self.assertEqual(loaded[0]["frames"], 160)
            clip["duration_sec"] = 10
            save()
            with self.assertRaisesRegex(ValueError, "duration mismatch"):
                load_manifest(manifest_path)
            clip["duration_sec"] = 0.01
            clip["audio_sha256"] = "0" * 64
            save()
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                load_manifest(manifest_path)
            clip["audio"] = str(audio)
            save()
            with self.assertRaisesRegex(ValueError, "relative"):
                load_manifest(manifest_path)
            subdirectory = base / "nested"
            subdirectory.mkdir()
            clip["audio"] = "../clip.wav"
            nested_manifest = subdirectory / "manifest.json"
            nested_manifest.write_text(json.dumps({"schema_version": 1, "clips": [clip]}))
            with self.assertRaisesRegex(ValueError, "escapes"):
                load_manifest(nested_manifest)


class ScheduleAndAggregationTests(unittest.TestCase):
    def test_seeded_interleaving_balances_configurations(self) -> None:
        models = [{"label": "tiny", "path": "/tiny"}, {"label": "base", "path": "/base"}]
        clips = [{"id": "one"}, {"id": "two"}]
        first = make_schedule(models, [1, 2], clips, 2, 42)
        self.assertEqual(first, make_schedule(models, [1, 2], clips, 2, 42))
        self.assertEqual(len(first), 16)
        for index in range(0, len(first), 4):
            block = first[index:index + 4]
            self.assertEqual(len({(task["clip"]["id"], task["repetition"]) for task in block}), 1)
            self.assertEqual({(task["model"]["label"], task["threads"]) for task in block},
                             {("tiny", 1), ("tiny", 2), ("base", 1), ("base", 2)})

    def test_micro_wer_and_incomplete_configuration(self) -> None:
        def success(reference: str, hypothesis: str, duration: int, latency: int) -> dict:
            return {"model": "tiny", "threads": 1, "status": "ok", "load_ms": 2,
                    "inference_ms": latency, "e2e_ms": latency + 5,
                    "inference_rtf": latency / duration, "e2e_rtf": (latency + 5) / duration,
                    "peak_rss_kb": 100 + latency, "audio_duration_ms": duration,
                    "accuracy": word_errors(reference, hypothesis)}
        trials = [success("one", "bad", 10, 10), success("one two three", "one two three", 30, 60),
                  {"model": "tiny", "threads": 1, "status": "failed"}]
        summary = aggregate(trials)[0]
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["failed_trials"], 1)
        self.assertEqual(summary["accuracy"]["wer"], 1 / 4)
        self.assertEqual(summary["inference_ms"], {"mean": 35, "median": 35})
        self.assertEqual(summary["peak_rss_kb_max"], 160)
        self.assertEqual(summary["inference_rtf_duration_weighted"], 70 / 40)


def write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * 160)


class NativeContractTests(unittest.TestCase):
    def run_cli(self, payload: dict, prefix: str = "", timeout: float = 10) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "fake-cli"
            executable.write_text(f"#!{sys.executable}\nimport json,time\n{prefix}\nprint({json.dumps(json.dumps(payload))})\n")
            executable.chmod(0o755)
            task = {"repetition": 1, "threads": 2,
                    "model": {"label": "tiny", "path": "/model.bin"},
                    "clip": {"id": "clip", "speaker": "one", "audio_path": "/clip.wav",
                             "duration_sec": 0.01, "reference": "ONE TWO"}}
            return execute_trial(executable, task, "en", timeout)

    @staticmethod
    def payload() -> dict:
        return {"text": "one two", "segments": [{"text": "one two", "start_ms": 0, "end_ms": 10}],
                "audio_duration_ms": 10, "load_ms": 1.0, "inference_ms": 2.0,
                "peak_rss_kb": 1234, "threads": 2, "backend_info": {"observed": "test"}}

    def test_native_json_and_unknown_backend_info_preserved(self) -> None:
        result = self.run_cli(self.payload())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["accuracy"]["wer"], 0)
        self.assertEqual(result["backend_info"], {"observed": "test"})
        self.assertGreater(result["e2e_ms"], 0)

    def test_invalid_native_metrics_are_failures(self) -> None:
        for key, value in (("load_ms", float("nan")), ("inference_ms", -1),
                           ("audio_duration_ms", 20), ("threads", 4), ("threads", True), ("peak_rss_kb", 10.5)):
            with self.subTest(key=key):
                payload = self.payload()
                payload[key] = value
                self.assertEqual(self.run_cli(payload)["status"], "failed")

    def test_unordered_timestamps_rejected_but_padding_not_hidden(self) -> None:
        payload = self.payload()
        payload["segments"][0]["end_ms"] = 20
        result = self.run_cli(payload)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["segments"][0]["end_ms"], 20)
        self.assertEqual(result["anomalies"][0]["kind"], "segment_exceeds_audio_duration")
        payload["segments"].append({"text": "backwards", "start_ms": 0, "end_ms": 5})
        self.assertEqual(self.run_cli(payload)["status"], "failed")

    def test_timeout_is_preserved_as_failure(self) -> None:
        result = self.run_cli(self.payload(), prefix="time.sleep(1)", timeout=0.01)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "timeout")

    @unittest.skipUnless(shutil.which("ldd") and Path("/bin/true").is_file(), "Linux ldd fixture required")
    def test_cli_failure_keeps_report_and_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            audio = base / "clip.wav"
            write_wav(audio)
            manifest = base / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "clips": [{
                "id": "one", "speaker": "one", "audio": "clip.wav", "reference": "one",
                "duration_sec": 0.01, "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest()}]}))
            model = base / "fixture.bin"
            model.write_bytes(b"protocol fixture, not model weights")
            output = base / "report.json"
            script = Path(__file__).resolve().parents[1] / "scripts" / "benchmark.py"
            # /bin/true succeeds without producing native JSON. That must fail
            # acceptance and retain a structured trial, rather than appear green.
            completed = subprocess.run([
                sys.executable, str(script), "--manifest", str(manifest),
                "--model", f"fixture={model}", "--threads", "1", "--repetitions", "1",
                "--executable", "/bin/true", "--output", str(output),
            ], capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 1)
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["expected_trials"], 1)
            self.assertEqual(report["trials"][0]["status"], "failed")
            self.assertEqual(report["summary"][0]["successful_trials"], 0)
            self.assertTrue(report["inputs"]["linked_libraries"]["libraries"])


if __name__ == "__main__":
    unittest.main()
