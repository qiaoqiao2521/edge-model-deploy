# Third-party sources

- whisper.cpp / GGML: https://github.com/ggml-org/whisper.cpp
  - Pinned submodule: `4979e04f5dcaccb36057e059bbaed8a2f5288315` (`v1.8.2`).
  - MIT license and copyright notices remain in the submodule.
  - The application links upstream code rather than copying the inference implementation.
- Multilingual Whisper GGML models: https://huggingface.co/ggerganov/whisper.cpp
  - Fixed model revision: `5359861c739e955e79d9a303bcbc70fb988958b1`.
  - See upstream model card and license; model weights are downloaded separately and are not committed.
- LibriSpeech: https://www.openslr.org/12/
  - Vassil Panayotov, Guoguo Chen, Daniel Povey, Sanjeev Khudanpur,
    “LibriSpeech: An ASR corpus based on public domain audio books,” ICASSP 2015.
  - Dataset license: CC BY 4.0. Only local selected audio and transcripts are prepared.
  - Archive integrity follows the MD5 published by OpenSLR; derived WAV files receive SHA-256 hashes.
