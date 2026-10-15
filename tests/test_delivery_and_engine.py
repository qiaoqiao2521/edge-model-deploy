import unittest
import shutil
import tempfile
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../python")))

from edge_model_deploy import DynamicModelManager, ModelTier, EdgeAudioPipeline


class TestDeliveryAndEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dynamic_delivery(self):
        mgr = DynamicModelManager(cache_dir=self.test_dir)
        self.assertFalse(mgr.is_available(ModelTier.TINY))
        path = mgr.ensure_model(ModelTier.TINY)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(mgr.is_available(ModelTier.TINY))

    def test_audio_pipeline(self):
        pipeline = EdgeAudioPipeline()
        raw = "那个……今天进行端侧转写测试"
        cleaned, segments, dropped = pipeline.process_transcript(raw, total_duration_sec=2.0)
        self.assertIn("今天进行端侧转写测试", cleaned)
        self.assertGreater(len(segments), 0)
        self.assertEqual(segments[0].start_ms, 0)
        self.assertEqual(segments[-1].end_ms, 2000)


if __name__ == "__main__":
    unittest.main()
