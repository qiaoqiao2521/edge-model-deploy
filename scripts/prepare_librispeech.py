#!/usr/bin/env python3
"""Prepare a deterministic 12-clip LibriSpeech test-clean smoke subset.

The full archive must match OpenSLR's published MD5. Only selected files are
read from the tar stream; archive paths are never extracted to the filesystem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from typing import Any
import wave


SOURCE_URL = "https://www.openslr.org/resources/12/test-clean.tar.gz"
CHECKSUM_URL = "https://www.openslr.org/resources/12/md5sum.txt"
EXPECTED_MD5 = "32fa31d27d2e1cad72775fee3f4849a9"
RESOURCE_URL = "https://www.openslr.org/12/"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
FLAC_PATTERN = re.compile(
    r"^LibriSpeech/test-clean/(\d+)/(\d+)/(\d+-\d+-\d+)\.flac$"
)


def digest_file(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_utterances(
    member_names: list[str], speakers: int = 4, utterances: int = 3
) -> list[str]:
    """Select numeric speaker order, then numeric (speaker, chapter, utterance)."""
    if speakers <= 0 or utterances <= 0:
        raise ValueError("sample counts must be positive")
    by_speaker: dict[int, list[str]] = {}
    for name in member_names:
        match = FLAC_PATTERN.fullmatch(name)
        if match:
            speaker, chapter, utterance_id = match.groups()
            parts = tuple(int(part) for part in utterance_id.split("-"))
            if parts[:2] != (int(speaker), int(chapter)):
                raise ValueError(f"inconsistent archive utterance path: {name}")
            by_speaker.setdefault(int(speaker), []).append(name)
    selected_speakers = sorted(by_speaker)[:speakers]
    if len(selected_speakers) != speakers:
        raise ValueError("archive does not contain the requested number of speakers")
    selected: list[str] = []
    for speaker in selected_speakers:
        candidates = sorted(
            by_speaker[speaker],
            key=lambda name: tuple(int(part) for part in Path(name).stem.split("-")),
        )
        if len(candidates) < utterances:
            raise ValueError(f"speaker {speaker} has fewer than {utterances} clips")
        selected.extend(candidates[:utterances])
    if len(set(selected)) != len(selected):
        raise ValueError("duplicate archive utterances")
    return selected


def wav_properties(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as audio:
        if (
            audio.getnchannels() != 1
            or audio.getframerate() != 16000
            or audio.getsampwidth() != 2
            or audio.getcomptype() != "NONE"
            or audio.getnframes() <= 0
        ):
            raise ValueError(f"audio must be nonempty PCM16 mono 16000 Hz: {path}")
        frames = audio.getnframes()
    return {"sample_rate_hz": 16000, "channels": 1, "sample_width_bytes": 2,
            "frames": frames, "duration_sec": frames / 16000.0}


def prepare(archive: Path, output: Path, ffmpeg: str = "ffmpeg") -> Path:
    archive = archive.resolve(strict=True)
    actual_md5 = digest_file(archive, "md5")
    if actual_md5 != EXPECTED_MD5:
        raise ValueError(f"OpenSLR archive MD5 mismatch: expected {EXPECTED_MD5}, got {actual_md5}")
    archive_sha256 = digest_file(archive)
    ffmpeg_version = subprocess.run(
        [ffmpeg, "-version"], check=True, capture_output=True, text=True,
        timeout=30,
    ).stdout.splitlines()[0]
    output.mkdir(parents=True, exist_ok=True)
    audio_dir = output / "audio"
    audio_dir.mkdir(exist_ok=True)
    clips: list[dict[str, Any]] = []
    with tarfile.open(archive, "r:gz") as corpus:
        regular = {member.name: member for member in corpus.getmembers() if member.isfile()}
        selected = select_utterances(list(regular))
        transcripts: dict[str, str] = {}
        transcript_members = {
            str(Path(name).parent / ("-".join(Path(name).stem.split("-")[:2]) + ".trans.txt"))
            for name in selected
        }
        for name in sorted(transcript_members):
            if name not in regular:
                raise ValueError(f"missing transcript: {name}")
            stream = corpus.extractfile(regular[name])
            if stream is None:
                raise ValueError(f"unreadable transcript: {name}")
            with stream:
                for line in stream.read().decode("utf-8").splitlines():
                    utterance_id, reference = line.split(maxsplit=1)
                    if utterance_id in transcripts:
                        raise ValueError(f"duplicate transcript: {utterance_id}")
                    transcripts[utterance_id] = reference
        for name in selected:
            utterance_id = Path(name).stem
            if not transcripts.get(utterance_id, "").strip():
                raise ValueError(f"missing nonempty reference: {utterance_id}")
            stream = corpus.extractfile(regular[name])
            if stream is None:
                raise ValueError(f"unreadable audio: {name}")
            with stream:
                source_bytes = stream.read()
            target = audio_dir / f"{utterance_id}.wav"
            with tempfile.TemporaryDirectory(dir=audio_dir) as temporary:
                converted = Path(temporary) / "converted.wav"
                command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                           "-i", "pipe:0", "-vn", "-ac", "1", "-ar", "16000",
                           "-c:a", "pcm_s16le", "-f", "wav", str(converted)]
                subprocess.run(command, input=source_bytes, check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                properties = wav_properties(converted)
                converted.replace(target)
            clips.append({
                "id": utterance_id, "speaker": utterance_id.split("-")[0],
                "audio": target.relative_to(output).as_posix(),
                "reference": transcripts[utterance_id],
                "audio_sha256": digest_file(target),
                "source_archive_member": name,
                "source_flac_sha256": hashlib.sha256(source_bytes).hexdigest(),
                **properties,
            })
    manifest = {
        "schema_version": 1,
        "dataset": "LibriSpeech test-clean deterministic smoke subset",
        "scope": "12 clips; smoke baseline only, not a representative corpus evaluation",
        "source": {"url": SOURCE_URL, "resource_url": RESOURCE_URL,
                   "checksum_url": CHECKSUM_URL, "archive_md5": actual_md5,
                   "archive_sha256": archive_sha256, "license": "CC BY 4.0",
                   "license_url": LICENSE_URL,
                   "attribution": "LibriSpeech: Vassil Panayotov, Guoguo Chen, Daniel Povey, Sanjeev Khudanpur (2015); audio derived from LibriVox",
                   "changes": "Deterministic subset; FLAC decoded to PCM16 mono 16000 Hz WAV"},
        "selection": {"speakers": 4, "utterances_per_speaker": 3,
                      "order": "numeric speaker; numeric (speaker, chapter, utterance)"},
        "conversion": {"ffmpeg_version": ffmpeg_version,
                       "arguments": ["-i", "pipe:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav"]},
        "clips": clips,
    }
    target_manifest = output / "manifest.json"
    temporary_manifest = output / "manifest.json.partial"
    temporary_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary_manifest.replace(target_manifest)
    return target_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True,
                        help="download test-clean.tar.gz from the fixed OpenSLR URL first")
    parser.add_argument("--output", type=Path, default=Path("data/librispeech-smoke"))
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    try:
        manifest = prepare(args.archive, args.output, args.ffmpeg)
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        parser.exit(1, f"preparation failed: {error}\n")
    print(json.dumps({"manifest": str(manifest.resolve()), "clips": 12}))


if __name__ == "__main__":
    main()
