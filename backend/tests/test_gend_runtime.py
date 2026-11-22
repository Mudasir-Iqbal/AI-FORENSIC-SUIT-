import unittest
from pathlib import Path


class GenDRuntimeSourceTests(unittest.TestCase):
    def test_runtime_is_isolated_from_production_requirements(self):
        requirements = Path("backend/requirements.txt").read_text()
        self.assertNotIn("torch==2.8.0", requirements)
        self.assertNotIn("transformers==4.56.2", requirements)

    def test_worker_pins_official_gen_d_artifacts(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn("DETECTOR_REPO_COMMIT =", source)
        self.assertIn("MODEL_REVISION =", source)
        self.assertIn("DETECTOR_MODEL_SHA256 =", source)
        self.assertIn("MODEL_SHA256 =", source)
        self.assertIn("sha256sum -c -", source)

    def test_worker_uses_official_retinaface_and_alignment_settings(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn("from detector import prepare_model", source)
        self.assertIn("prepare_model(det_thres=DETECTOR_THRESHOLD, nms_thresh=NMS_THRESHOLD)", source)
        self.assertIn("DETECTOR_THRESHOLD = 0.1", source)
        self.assertIn("NMS_THRESHOLD = 0.4", source)
        self.assertIn("DETECTOR_INPUT_SIZE = (640, 640)", source)
        self.assertIn("target_size=None", source)
        self.assertIn("scale=ALIGNMENT_SCALE", source)
        self.assertIn("ALIGNMENT_SCALE = 1.3", source)

    def test_worker_uses_official_sampling_and_clip_preprocessing(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn('mode="at_least"', source)
        self.assertIn("num_frames=TARGET_FACE_FRAMES", source)
        self.assertIn("model.feature_extractor.preprocess(aligned_image)", source)
        self.assertIn("TARGET_FACE_FRAMES = 32", source)

    def test_worker_preserves_class_mapping_and_withholds_uncalibrated_verdict(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn('"class_0": "real"', source)
        self.assertIn('"class_1": "fake"', source)
        self.assertIn('"verdict_status": "not_assessed_threshold_requires_independent_validation"', source)
        self.assertIn('"frame_aggregation": "arithmetic_mean_of_per_frame_softmax_probabilities"', source)

    def test_worker_has_bounded_inputs_and_research_license_notice(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn("MAX_VIDEO_BYTES = 250 * 1024 * 1024", source)
        self.assertIn("MAX_SOURCE_FRAMES = 1800", source)
        self.assertIn("non-commercial research use", source)


if __name__ == "__main__":
    unittest.main()
