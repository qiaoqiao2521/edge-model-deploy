"""Network-isolated tests for verified model cache replacement."""

import hashlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../python")))

from edge_model_deploy.delivery import (
    DEFAULT_MODEL_SPECS,
    DynamicModelManager,
    ModelSpec,
    ModelTier,
    ModelVerificationError,
    _HTTPSOnlyRedirectHandler,
)


class FakeResponse(io.BytesIO):
    def __init__(self, payload, content_length=None, fail_after=None):
        super().__init__(payload)
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}
        self.fail_after = fail_after
        self.read_sizes = []

    def geturl(self):
        return "https://example.test/model.bin"

    def read(self, size=-1):
        self.read_sizes.append(size)
        if self.fail_after is not None and self.tell() >= self.fail_after:
            raise ConnectionResetError("fixture connection interrupted")
        if self.fail_after is not None:
            size = min(size, self.fail_after - self.tell())
        return super().read(size)


class TestModelDelivery(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.payload = b"verified fixture model"
        self.spec = ModelSpec(
            "https://example.test/model.bin", len(self.payload),
            hashlib.sha256(self.payload).hexdigest(),
        )
        self.manager = DynamicModelManager(
            self.directory.name, model_specs={ModelTier.TINY: self.spec},
        )
        self.path = self.manager.get_model_path(ModelTier.TINY)

    def write_cache(self, payload):
        with open(self.path, "wb") as model:
            model.write(payload)

    def assert_no_partials(self):
        self.assertFalse(any(name.endswith(".part") for name in os.listdir(self.directory.name)))

    def test_valid_cache_never_opens_network(self):
        self.write_cache(self.payload)
        progress = []
        with patch("edge_model_deploy.delivery._open_https") as opener:
            self.assertEqual(self.manager.ensure_model(ModelTier.TINY, progress.append), self.path)
            opener.assert_not_called()
        self.assertEqual(progress, [1.0])

    def test_size_and_hash_are_both_checked_for_cache(self):
        for invalid in (b"GGML_EDGE_WHISPER_WEIGHTS_V1\n", b"!" * len(self.payload)):
            with self.subTest(invalid=invalid):
                self.write_cache(invalid)
                self.assertFalse(self.manager.is_available(ModelTier.TINY))

    def test_corrupt_cache_is_replaced_after_verified_download(self):
        self.write_cache(b"old invalid content")
        progress = []
        response = FakeResponse(self.payload, len(self.payload))
        with patch("edge_model_deploy.delivery._open_https", return_value=response) as opener:
            self.assertEqual(self.manager.ensure_model(ModelTier.TINY, progress.append), self.path)
            opener.assert_called_once_with(self.spec.url, self.manager.timeout)
        self.assertTrue(self.manager.is_available(ModelTier.TINY))
        self.assertEqual(progress[-1], 1.0)
        self.assertNotIn(1.0, progress[:-1])
        self.assert_no_partials()

    def test_bad_size_or_hash_preserves_existing_file(self):
        old_bytes = b"keep existing file on failed replacement"
        for body in (self.payload[:-1], self.payload + b"extra", b"!" * len(self.payload)):
            with self.subTest(body=body):
                self.write_cache(old_bytes)
                progress = []
                response = FakeResponse(body)
                with patch("edge_model_deploy.delivery._open_https", return_value=response):
                    with self.assertRaises(ModelVerificationError):
                        self.manager.ensure_model(ModelTier.TINY, progress.append)
                with open(self.path, "rb") as model:
                    self.assertEqual(model.read(), old_bytes)
                self.assertNotIn(1.0, progress)
                self.assert_no_partials()

    def test_oversized_response_reads_at_most_expected_size_plus_one(self):
        response = FakeResponse(self.payload + b"extra bytes")
        with patch("edge_model_deploy.delivery._open_https", return_value=response):
            with self.assertRaisesRegex(ModelVerificationError, "exceeds"):
                self.manager.ensure_model(ModelTier.TINY)
        self.assertEqual(response.read_sizes, [len(self.payload) + 1])
        self.assertFalse(os.path.exists(self.path))
        self.assert_no_partials()

    def test_content_length_mismatch_rejected_before_body_read(self):
        response = FakeResponse(self.payload, len(self.payload) + 1)
        with patch("edge_model_deploy.delivery._open_https", return_value=response):
            with self.assertRaisesRegex(ModelVerificationError, "Content-Length"):
                self.manager.ensure_model(ModelTier.TINY)
        self.assertEqual(response.read_sizes, [])
        self.assert_no_partials()

    def test_network_interruption_preserves_file_and_cleans_partial(self):
        old_bytes = b"previous invalid model"
        self.write_cache(old_bytes)
        progress = []
        response = FakeResponse(self.payload, fail_after=3)
        with patch("edge_model_deploy.delivery._open_https", return_value=response):
            with self.assertRaises(ConnectionResetError):
                self.manager.ensure_model(ModelTier.TINY, progress.append)
        with open(self.path, "rb") as model:
            self.assertEqual(model.read(), old_bytes)
        self.assertNotIn(1.0, progress)
        self.assert_no_partials()

    def test_connection_failure_cleans_partial(self):
        with patch("edge_model_deploy.delivery._open_https", side_effect=TimeoutError("timed out")):
            with self.assertRaises(TimeoutError):
                self.manager.ensure_model(ModelTier.TINY)
        self.assertFalse(os.path.exists(self.path))
        self.assert_no_partials()

    def test_total_timeout_cleans_partial(self):
        with patch("edge_model_deploy.delivery._open_https", return_value=FakeResponse(self.payload)):
            with patch("edge_model_deploy.delivery.time.monotonic", side_effect=[0.0, 1000.0]):
                with self.assertRaises(TimeoutError):
                    self.manager.ensure_model(ModelTier.TINY)
        self.assertFalse(os.path.exists(self.path))
        self.assert_no_partials()

    def test_atomic_replace_failure_preserves_existing_file(self):
        self.write_cache(b"original")
        progress = []
        with patch("edge_model_deploy.delivery._open_https", return_value=FakeResponse(self.payload)):
            with patch("edge_model_deploy.delivery.os.replace", side_effect=OSError("disk error")):
                with self.assertRaises(OSError):
                    self.manager.ensure_model(ModelTier.TINY, progress.append)
        with open(self.path, "rb") as model:
            self.assertEqual(model.read(), b"original")
        self.assertNotIn(1.0, progress)
        self.assert_no_partials()

    def test_http_url_or_redirect_rejected(self):
        with self.assertRaises(ValueError):
            ModelSpec("http://example.test/model", 1, "0" * 64)
        with self.assertRaises(ValueError):
            _HTTPSOnlyRedirectHandler().redirect_request(
                None, None, 302, "found", {}, "http://example.test/model",
            )

    def test_invalid_size_digest_and_timeouts_rejected(self):
        for invalid_size in (0, -1, True, 1.5):
            with self.subTest(size=invalid_size):
                with self.assertRaises(ValueError):
                    ModelSpec("https://example.test/model", invalid_size, "0" * 64)
        with self.assertRaises(ValueError):
            ModelSpec("https://example.test/model", 1, "not-a-digest")
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    DynamicModelManager(self.directory.name, timeout=timeout)

    def test_defaults_are_pinned_multilingual_models(self):
        for spec in DEFAULT_MODEL_SPECS.values():
            self.assertIn("/5359861c739e955e79d9a303bcbc70fb988958b1/", spec.url)
            self.assertNotIn(".en.bin", spec.url)


if __name__ == "__main__":
    unittest.main()
