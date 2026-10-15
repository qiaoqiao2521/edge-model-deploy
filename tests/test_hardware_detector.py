import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../python")))

from edge_model_deploy import HardwareDetector, HardwareProfile


class TestHardwareDetector(unittest.TestCase):
    def test_detection_types(self):
        detector = HardwareDetector()
        profile = detector.get_profile()
        self.assertIsInstance(profile, HardwareProfile)
        self.assertIn(profile.arch, ["ARM64", "ARM32", "X86_64", "UNKNOWN"])
        self.assertTrue(profile.recommended_library.endswith(".so"))


if __name__ == "__main__":
    unittest.main()
