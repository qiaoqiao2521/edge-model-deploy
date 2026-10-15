"""Download pinned whisper.cpp models and verify every cache lookup."""

import hashlib
import math
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import BinaryIO, Callable, Mapping, Optional


class ModelTier(Enum):
    TINY = "whisper-tiny"
    BASE = "whisper-base"


@dataclass(frozen=True)
class ModelSpec:
    """Trusted metadata; custom models still require HTTPS, size and SHA-256."""

    url: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlparse(self.url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Model URL must use HTTPS")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes <= 0:
            raise ValueError("Model size must be a positive integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Model SHA-256 must contain 64 lowercase hex digits")


# The upstream download-ggml-model.sh names this model repository.
# Fixed revision and LFS metadata were checked against:
# https://huggingface.co/api/models/ggerganov/whisper.cpp/revision/
# 5359861c739e955e79d9a303bcbc70fb988958b1?blobs=true
MODEL_REVISION = "5359861c739e955e79d9a303bcbc70fb988958b1"
_MODEL_BASE_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/" + MODEL_REVISION
)
DEFAULT_MODEL_SPECS = {
    ModelTier.TINY: ModelSpec(
        _MODEL_BASE_URL + "/ggml-tiny.bin",
        77691713,
        "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
    ),
    ModelTier.BASE: ModelSpec(
        _MODEL_BASE_URL + "/ggml-base.bin",
        147951465,
        "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
    ),
}
_CHUNK_SIZE = 1024 * 1024


class ModelVerificationError(ValueError):
    """A downloaded file does not match trusted model metadata."""


class _HTTPSOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).scheme != "https":
            raise ValueError("Refusing model download redirect outside HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_https(url: str, timeout: float) -> BinaryIO:
    opener = urllib.request.build_opener(_HTTPSOnlyRedirectHandler())
    request = urllib.request.Request(
        url, headers={"User-Agent": "edge-model-deploy/0.1", "Accept-Encoding": "identity"}
    )
    return opener.open(request, timeout=timeout)


class DynamicModelManager:
    """Fetch multilingual Tiny/Base weights into an integrity-checked cache.

    ``timeout`` bounds each socket operation. ``download_timeout`` bounds the
    complete transfer between reads; one socket operation may finish later.
    Failed transfers never replace the previous destination file.
    """

    def __init__(
        self,
        cache_dir: str = "./models",
        *,
        model_specs: Optional[Mapping[ModelTier, ModelSpec]] = None,
        timeout: float = 30.0,
        download_timeout: float = 900.0,
    ):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Socket timeout must be finite and positive")
        if not math.isfinite(download_timeout) or download_timeout <= 0:
            raise ValueError("Download timeout must be finite and positive")
        self.cache_dir = os.path.abspath(cache_dir)
        self.model_specs = dict(DEFAULT_MODEL_SPECS)
        if model_specs is not None:
            self.model_specs.update(model_specs)
        self.timeout = timeout
        self.download_timeout = download_timeout
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_model_path(self, tier: ModelTier) -> str:
        return os.path.join(self.cache_dir, "{}.bin".format(tier.value))

    def is_available(self, tier: ModelTier) -> bool:
        spec = self.model_specs[tier]
        try:
            with open(self.get_model_path(tier), "rb") as model:
                if os.fstat(model.fileno()).st_size != spec.size_bytes:
                    return False
                digest = hashlib.sha256()
                size = 0
                while size <= spec.size_bytes:
                    chunk = model.read(min(_CHUNK_SIZE, spec.size_bytes - size + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    digest.update(chunk)
                return size == spec.size_bytes and digest.hexdigest() == spec.sha256
        except OSError:
            return False

    def ensure_model(
        self,
        tier: ModelTier,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> str:
        path = self.get_model_path(tier)
        if self.is_available(tier):
            if progress_callback:
                progress_callback(1.0)
            return path

        spec = self.model_specs[tier]
        deadline = time.monotonic() + self.download_timeout
        temporary_path = None
        try:
            # A unique file in the destination directory keeps replace atomic.
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.cache_dir,
                prefix=".{}.".format(tier.value), suffix=".part", delete=False,
            ) as output:
                temporary_path = output.name
                with _open_https(spec.url, self.timeout) as response:
                    if urllib.parse.urlparse(response.geturl()).scheme != "https":
                        raise ValueError("Model response must use HTTPS")
                    content_length = response.headers.get("Content-Length")
                    if content_length is not None and int(content_length) != spec.size_bytes:
                        raise ModelVerificationError("Model Content-Length does not match expected size")
                    digest = hashlib.sha256()
                    size = 0
                    if progress_callback:
                        progress_callback(0.0)
                    while True:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Model download exceeded total time limit")
                        # Read at most expected size + one byte, even without headers.
                        chunk = response.read(min(_CHUNK_SIZE, spec.size_bytes - size + 1))
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > spec.size_bytes:
                            raise ModelVerificationError("Model exceeds expected size")
                        output.write(chunk)
                        digest.update(chunk)
                        if progress_callback:
                            # 1.0 is reserved for verified, atomically installed models.
                            progress_callback(min(size / spec.size_bytes, 0.999))
                    if size != spec.size_bytes:
                        raise ModelVerificationError("Model size does not match expected size")
                    if digest.hexdigest() != spec.sha256:
                        raise ModelVerificationError("Model SHA-256 does not match expected digest")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass

        if progress_callback:
            progress_callback(1.0)
        return path
