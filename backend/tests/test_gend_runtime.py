import unittest

from pathlib import Path


class GenDRuntimeSourceTests(unittest.TestCase):
    def test_runtime_is_isolated_from_production_requirements(self):
        requirements = Path("backend/requirements.txt").read_text()
        self.assertNotIn("torch==2.8.0", requirements)
        self.assertNotIn("transformers==4.56.2", requirements)

    def test_worker_keeps_unvalidated_preprocessing_experimental(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn('"verdict_status": "not_assessed"', source)
        self.assertIn("not_official_detector_validated", source)
        self.assertIn("class_0_real", source)
        self.assertIn("class_1_fake", source)

    def test_worker_has_bounded_inputs(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn("MAX_CROPS = 120", source)
        self.assertIn("MAX_BATCH_BYTES = 32 * 1024 * 1024", source)
        self.assertIn("MAX_CROP_BYTES = 2 * 1024 * 1024", source)


if __name__ == "__main__":
    unittest.main()
