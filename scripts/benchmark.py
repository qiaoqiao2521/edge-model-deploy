#!/usr/bin/env python3
"""Measure a small independent-process ASR baseline with explicit provenance.

This does not control operating-system caches or temperature. Every trial starts
a new process; neither "warm cache" nor "cold cache" is inferred from that fact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import statistics
import string
import subprocess
import sys
import time
from typing import Any

try:
    from .prepare_librispeech import digest_file, wav_properties
except ImportError:
    from prepare_librispeech import digest_file, wav_properties


NORMALIZATION = (
    "lowercase; curly apostrophes mapped to ASCII apostrophe; apostrophes deleted "
    "within words (don't -> dont); other ASCII punctuation replaced with spaces "
    "to preserve word boundaries; split on whitespace; no number expansion"
)


def reject_nonfinite_json(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"nonfinite JSON number: {value}")
    return parsed


def normalize_words(text: str) -> list[str]:
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    table = {ord(character): ("" if character == "'" else " ")
             for character in string.punctuation}
    return text.translate(table).split()


def word_errors(reference: str, hypothesis: str) -> dict[str, Any]:
    """Levenshtein WER; ties prefer substitution, deletion, then insertion."""
    expected, actual = normalize_words(reference), normalize_words(hypothesis)
    if not expected:
        raise ValueError("reference has no words after normalization")
    distances = [[0] * (len(actual) + 1) for _ in range(len(expected) + 1)]
    for row in range(len(expected) + 1):
        distances[row][0] = row
    for column in range(len(actual) + 1):
        distances[0][column] = column
    for row in range(1, len(expected) + 1):
        for column in range(1, len(actual) + 1):
            distances[row][column] = min(
                distances[row - 1][column - 1] + (expected[row - 1] != actual[column - 1]),
                distances[row - 1][column] + 1,
                distances[row][column - 1] + 1,
            )
    row, column = len(expected), len(actual)
    substitutions = deletions = insertions = 0
    while row or column:
        if row and column and expected[row - 1] == actual[column - 1] and distances[row][column] == distances[row - 1][column - 1]:
            row, column = row - 1, column - 1
        elif row and column and distances[row][column] == distances[row - 1][column - 1] + 1:
            substitutions += 1
            row, column = row - 1, column - 1
        elif row and distances[row][column] == distances[row - 1][column] + 1:
            deletions += 1
            row -= 1
        else:
            insertions += 1
            column -= 1
    errors = substitutions + deletions + insertions
    return {"substitutions": substitutions, "deletions": deletions,
            "insertions": insertions, "errors": errors,
            "reference_words": len(expected), "wer": errors / len(expected)}


def load_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(path.read_text(encoding="utf-8"),
                          parse_constant=reject_nonfinite_json, parse_float=finite_json_float)
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema_version")
    clips = manifest.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("manifest must contain a nonempty clips list")
    base = path.resolve().parent
    seen: set[str] = set()
    loaded = []
    for clip in clips:
        for field in ("id", "speaker", "audio", "reference", "audio_sha256"):
            if not isinstance(clip.get(field), str) or not clip[field]:
                raise ValueError(f"missing string clip field: {field}")
        if clip["id"] in seen:
            raise ValueError(f"duplicate clip id: {clip['id']}")
        seen.add(clip["id"])
        relative = Path(clip["audio"])
        if relative.is_absolute():
            raise ValueError("manifest audio paths must be relative")
        audio = (base / relative).resolve(strict=True)
        try:
            audio.relative_to(base)
        except ValueError:
            raise ValueError("manifest audio path escapes its directory")
        actual_sha = digest_file(audio)
        if actual_sha != clip["audio_sha256"]:
            raise ValueError(f"audio SHA256 mismatch: {clip['id']}")
        properties = wav_properties(audio)
        recorded_duration = clip.get("duration_sec")
        if isinstance(recorded_duration, bool) or not isinstance(recorded_duration, (int, float)) or not math.isfinite(recorded_duration) or abs(recorded_duration - properties["duration_sec"]) > 1 / 16000:
            raise ValueError(f"manifest duration mismatch: {clip['id']}")
        word_errors(clip["reference"], "")
        loaded.append({**clip, "audio_path": str(audio), **properties})
    return manifest, loaded


def make_schedule(
    models: list[dict[str, str]], threads: list[int], clips: list[dict[str, Any]],
    repetitions: int, seed: int,
) -> list[dict[str, Any]]:
    """Shuffle clip/repetition blocks and configurations with one fixed seed."""
    if repetitions < 1 or not threads or any(value < 1 for value in threads):
        raise ValueError("positive repetitions and threads are required")
    randomizer = random.Random(seed)
    blocks = [(repetition, clip) for repetition in range(1, repetitions + 1) for clip in clips]
    randomizer.shuffle(blocks)
    configurations = [(model, value) for model in models for value in threads]
    schedule = []
    for repetition, clip in blocks:
        order = configurations.copy()
        randomizer.shuffle(order)
        for model, value in order:
            schedule.append({"repetition": repetition, "clip": clip,
                             "model": model, "threads": value})
    return schedule


def git_provenance(directory: Path) -> dict[str, Any]:
    def git(*arguments: str) -> bytes:
        return subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                              capture_output=True, timeout=30).stdout
    try:
        root = Path(git("rev-parse", "--show-toplevel").decode().strip())
        head = git("rev-parse", "HEAD").decode().strip()
        status = git("status", "--porcelain=v1", "-z")
        patch = git("diff", "--binary", "HEAD", "--")
        untracked = git("ls-files", "--others", "--exclude-standard", "-z")
        submodules = git("submodule", "status", "--recursive").decode().splitlines()
        files = []
        for name in untracked.decode().split("\0"):
            if not name:
                continue
            path = root / name
            if path.is_file() and not path.is_symlink():
                files.append({"path": name, "sha256": digest_file(path)})
            else:
                files.append({"path": name, "sha256": None})
        return {"available": True, "root": str(root), "head": head,
                "dirty": bool(status), "status_porcelain": status.decode().replace("\0", "\n"),
                "tracked_patch_sha256": hashlib.sha256(patch).hexdigest(),
                "untracked_files": files,
                "submodule_status_recursive": submodules,
                "note": "HEAD alone does not identify dirty source. Patch and untracked-file hashes record the observed worktree; they do not prove how an existing executable was built."}
    except (OSError, subprocess.SubprocessError) as error:
        return {"available": False, "reason": str(error)}


def binary_dependencies(executable: Path) -> dict[str, Any]:
    """Hash ldd-resolved shared objects; the CLI hash alone omits inference code."""
    completed = subprocess.run(["ldd", str(executable)], check=True,
                               capture_output=True, text=True, timeout=30)
    if "not found" in completed.stdout:
        raise ValueError("executable has unresolved shared library dependencies")
    libraries = []
    seen: set[str] = set()
    for line in completed.stdout.splitlines():
        match = re.search(r"(?:=>\s+)?(/\S+)\s+\(", line)
        if match:
            path = Path(match.group(1)).resolve(strict=True)
            if str(path) not in seen:
                seen.add(str(path))
                libraries.append({"path": str(path), "sha256": digest_file(path)})
    return {"method": "ldd resolved linked libraries; does not enumerate later dlopen plugins",
            "libraries": sorted(libraries, key=lambda item: item["path"])}


def build_configuration(executable: Path) -> dict[str, Any]:
    cache = executable.parent / "CMakeCache.txt"
    if not cache.is_file():
        return {"available": False, "reason": "CMakeCache.txt absent next to executable"}
    selected = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("//", "#")) or "=" not in line:
            continue
        declaration, value = line.split("=", 1)
        key = declaration.split(":", 1)[0]
        if key.startswith(("GGML_", "WHISPER_", "EDGE_", "OpenMP_", "CMAKE_CXX_FLAGS", "CMAKE_C_FLAGS")) or key in ("CMAKE_BUILD_TYPE", "CMAKE_C_COMPILER", "CMAKE_CXX_COMPILER", "CMAKE_GENERATOR"):
            selected[key] = value
    return {"available": True, "path": str(cache), "sha256": digest_file(cache),
            "selected_values": selected,
            "note": "Observed build cache; binary hashes identify measured artifacts. Cache contents do not prove a particular executable was rebuilt."}


def environment_info() -> dict[str, Any]:
    cpu_names: set[str] = set()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                if key.strip() in ("model name", "Hardware", "Processor"):
                    cpu_names.add(value.strip())
    return {"platform": platform.platform(), "uname": list(platform.uname()),
            "python": sys.version, "python_executable": sys.executable,
            "cpu_names": sorted(cpu_names), "logical_cpu_count": os.cpu_count(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "selected_environment": {name: os.environ.get(name) for name in (
                "OMP_NUM_THREADS", "OMP_PROC_BIND", "OMP_PLACES", "OMP_DYNAMIC",
                "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS",
                "GGML_N_THREADS", "GGML_SCHED_DEBUG", "CUDA_VISIBLE_DEVICES")}}


def execute_trial(
    executable: Path, task: dict[str, Any], language: str, timeout: float,
) -> dict[str, Any]:
    clip, model, threads = task["clip"], task["model"], task["threads"]
    command = [str(executable), "--model", model["path"], "--audio", clip["audio_path"],
               "--language", language, "--threads", str(threads)]
    result: dict[str, Any] = {
        "model": model["label"], "threads": threads, "clip_id": clip["id"],
        "speaker": clip["speaker"], "repetition": task["repetition"],
        "audio_duration_ms": clip["duration_sec"] * 1000,
        "reference": clip["reference"], "argv": command,
    }
    started = time.perf_counter()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        # subprocess.run returns after waiting and reading pipes. Hashing and JSON
        # parsing happen outside this end-to-end interval.
        result["e2e_ms"] = (time.perf_counter() - started) * 1000
        result["returncode"] = completed.returncode
        if completed.returncode:
            result.update(status="failed", error="nonzero_exit", stderr_tail=completed.stderr[-2000:])
            return result
        payload = json.loads(completed.stdout, parse_constant=reject_nonfinite_json,
                             parse_float=finite_json_float)
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str) or not isinstance(payload.get("segments"), list):
            raise ValueError("CLI JSON must contain text and segments")
        for field in ("load_ms", "inference_ms", "audio_duration_ms", "peak_rss_kb"):
            value = payload.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid CLI metric: {field}")
        if payload["peak_rss_kb"] == 0 or payload["audio_duration_ms"] <= 0:
            raise ValueError("CLI RSS and audio duration must be positive")
        if not isinstance(payload["peak_rss_kb"], int):
            raise ValueError("CLI peak_rss_kb must be an integer")
        if abs(payload["audio_duration_ms"] - result["audio_duration_ms"]) > 1:
            raise ValueError("CLI audio duration disagrees with manifest")
        if isinstance(payload.get("threads"), bool) or not isinstance(payload.get("threads"), int) or payload["threads"] != threads:
            raise ValueError("CLI threads disagree with requested threads")
        if "backend_info" not in payload:
            raise ValueError("CLI JSON is missing backend_info")
        anomalies = []
        previous_start = previous_end = 0
        for segment in payload["segments"]:
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                raise ValueError("CLI segments require text and integer start_ms/end_ms")
            start, end = segment.get("start_ms"), segment.get("end_ms")
            if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end)):
                raise ValueError("CLI segment timestamps must be integers")
            if start < 0 or end < start or start < previous_start or end < previous_end:
                raise ValueError("CLI segment timestamps must be nonnegative and ordered")
            previous_start, previous_end = start, end
            if end > payload["audio_duration_ms"] + 1:
                anomalies.append({"kind": "segment_exceeds_audio_duration", "start_ms": start, "end_ms": end})
        result.update(status="ok", hypothesis=payload["text"], segments=payload["segments"],
                      load_ms=payload["load_ms"], inference_ms=payload["inference_ms"],
                      peak_rss_kb=payload["peak_rss_kb"], backend_info=payload["backend_info"],
                      inference_rtf=payload["inference_ms"] / result["audio_duration_ms"],
                      e2e_rtf=result["e2e_ms"] / result["audio_duration_ms"],
                      accuracy=word_errors(clip["reference"], payload["text"]),
                      anomalies=anomalies)
    except subprocess.TimeoutExpired:
        result.update(status="failed", error="timeout", timeout_sec=timeout,
                      e2e_ms=(time.perf_counter() - started) * 1000)
    except (OSError, ValueError, TypeError) as error:
        result.update(status="failed", error=type(error).__name__, detail=str(error))
    return result


def aggregate(trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configurations = sorted({(trial["model"], trial["threads"]) for trial in trials})
    summaries = []
    for label, threads in configurations:
        selected = [trial for trial in trials if (trial["model"], trial["threads"]) == (label, threads)]
        successful = [trial for trial in selected if trial["status"] == "ok"]
        summary: dict[str, Any] = {"model": label, "threads": threads,
                                   "attempted_trials": len(selected), "successful_trials": len(successful),
                                   "failed_trials": len(selected) - len(successful),
                                   "complete": len(selected) == len(successful),
                                   "metrics_scope": "successful trials only; incomplete configurations are not comparable"}
        if successful:
            for metric in ("load_ms", "inference_ms", "e2e_ms", "inference_rtf", "e2e_rtf"):
                values = [trial[metric] for trial in successful]
                summary[metric] = {"mean": statistics.mean(values), "median": statistics.median(values)}
            summary["peak_rss_kb_max"] = max(trial["peak_rss_kb"] for trial in successful)
            totals = {key: sum(trial["accuracy"][key] for trial in successful)
                      for key in ("substitutions", "deletions", "insertions", "errors", "reference_words")}
            totals["wer"] = totals["errors"] / totals["reference_words"]
            totals["scope"] = "micro WER over successful repeated trials; each repetition counts its reference words"
            summary["accuracy"] = totals
            summary["audio_duration_ms_total"] = sum(trial["audio_duration_ms"] for trial in successful)
            summary["inference_rtf_duration_weighted"] = sum(trial["inference_ms"] for trial in successful) / summary["audio_duration_ms_total"]
            summary["e2e_rtf_duration_weighted"] = sum(trial["e2e_ms"] for trial in successful) / summary["audio_duration_ms_total"]
        summaries.append(summary)
    return summaries


def write_result(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--threads", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument("--timeout", type=float, default=300, help="seconds per independent subprocess")
    parser.add_argument("--language", default="en")
    parser.add_argument("--executable", type=Path, default=Path("build-native/edge-transcribe"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.timeout <= 0 or not math.isfinite(args.timeout):
            raise ValueError("timeout must be finite and positive")
        if len(set(args.threads)) != len(args.threads):
            raise ValueError("duplicate thread configuration")
        manifest_path = args.manifest.resolve(strict=True)
        executable = args.executable.resolve(strict=True)
        if not os.access(executable, os.X_OK):
            raise ValueError("executable is not executable")
        manifest, clips = load_manifest(manifest_path)
        models = []
        for specification in args.model:
            label, separator, name = specification.partition("=")
            if not separator or not label.strip() or not name:
                raise ValueError("model must have the form LABEL=PATH")
            model_path = Path(name).resolve(strict=True)
            if any(model["label"] == label for model in models):
                raise ValueError(f"duplicate model label: {label}")
            models.append({"label": label, "path": str(model_path), "sha256": digest_file(model_path)})
        schedule = make_schedule(models, args.threads, clips, args.repetitions, args.seed)
        executable_sha = digest_file(executable)
        dependencies = binary_dependencies(executable)
        configuration = build_configuration(executable)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f"benchmark setup failed: {error}\n")
    report: dict[str, Any] = {
        "schema_version": 1, "status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "smoke baseline; small deterministic sample, no statistical generalization or scheduler claim",
        "protocol": {"seed": args.seed, "repetitions": args.repetitions,
                     "language": args.language, "threads": args.threads,
                     "timeout_sec": args.timeout, "normalization": NORMALIZATION,
                     "order": "seeded shuffled clip/repetition blocks, independently shuffled configurations per block",
                     "process": "one independent process per trial; model loading occurs every trial",
                     "cache": "OS/page caches are uncontrolled; no cold/warm cache claim",
                     "e2e": "wall time around subprocess launch, execution, wait, pipe reads; excludes input hashes and JSON parsing",
                     "rss": "peak_rss_kb reported by CLI for its own process lifetime, including load and inference; not system memory or incremental model memory"},
        "argv": sys.argv, "environment": environment_info(),
        "source_git": git_provenance(Path(__file__).resolve().parent),
        "inputs": {"manifest_path": str(manifest_path), "manifest_sha256": digest_file(manifest_path),
                   "manifest": manifest, "models": models,
                   "executable": {"path": str(executable), "sha256": executable_sha},
                   "linked_libraries": dependencies,
                   "build_configuration": configuration},
        "trials": [],
    }
    write_result(args.output, report)
    interrupted = False
    try:
        for index, task in enumerate(schedule):
            trial = execute_trial(executable, task, args.language, args.timeout)
            trial["order_index"] = index
            report["trials"].append(trial)
            # Preserve partial results without printing logs or dropping failures.
            write_result(args.output, report)
    except KeyboardInterrupt:
        interrupted = True
    changed_inputs = []
    expected_hashes = [(executable, executable_sha), (manifest_path, report["inputs"]["manifest_sha256"])]
    expected_hashes.extend((Path(model["path"]), model["sha256"]) for model in models)
    expected_hashes.extend((Path(library["path"]), library["sha256"]) for library in dependencies["libraries"])
    if configuration["available"]:
        expected_hashes.append((Path(configuration["path"]), configuration["sha256"]))
    expected_hashes.extend((Path(clip["audio_path"]), clip["audio_sha256"]) for clip in clips)
    for path, expected in expected_hashes:
        try:
            unchanged = digest_file(path) == expected
        except OSError:
            unchanged = False
        if not unchanged:
            changed_inputs.append(str(path))
    report.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),
                  expected_trials=len(schedule), interrupted=interrupted,
                  changed_inputs=changed_inputs, summary=aggregate(report["trials"]))
    failed = interrupted or bool(changed_inputs) or any(trial["status"] != "ok" for trial in report["trials"])
    report["status"] = "failed" if failed else "complete"
    write_result(args.output, report)
    print(json.dumps({"output": str(args.output.resolve()), "status": report["status"],
                      "trials": len(report["trials"]), "expected_trials": len(schedule)}))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
