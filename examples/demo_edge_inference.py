#!/usr/bin/env python3
"""Download verified weights and transcribe a real WAV through the C++ backend."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from edge_model_deploy import DynamicModelManager, ModelTier, WhisperTranscriber


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True, help='16 kHz mono PCM16 WAV')
    parser.add_argument('--model', choices=['tiny', 'base'], default='tiny')
    parser.add_argument('--language', default='zh')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--executable', type=Path, default=ROOT / 'build-native' / 'edge-transcribe')
    parser.add_argument('--cache-dir', type=Path, default=ROOT / 'models')
    args = parser.parse_args()
    transcriber = WhisperTranscriber(args.executable)
    manager = DynamicModelManager(str(args.cache_dir))
    tier = ModelTier.TINY if args.model == 'tiny' else ModelTier.BASE
    model_path = manager.ensure_model(tier)
    result = transcriber.transcribe(model_path, args.audio, language=args.language, threads=args.threads)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
