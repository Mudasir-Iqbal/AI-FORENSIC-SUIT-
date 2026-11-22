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

    def test_worker_accepts_short_clips_and_hashes_the_original_upload(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertNotIn("if source_frame_count < TARGET_FACE_FRAMES:", source)
        self.assertIn('source_video_sha256 = hashlib.sha256(video_bytes).hexdigest()', source)
        self.assertIn("if source_frame_count < 1:", source)
        self.assertIn("MIN_FACE_FRAMES_FOR_ASSESSMENT = 8", source)

    def test_worker_validates_extension_and_retinaface_landmarks(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertIn("Unsupported video extension.", source)
        self.assertIn("if landmarks is None or len(landmarks) != len(boxes):", source)

    def test_worker_preflights_video_before_loading_large_models(self):
        source = Path("backend/modal_gend_app.py").read_text()
        self.assertLess(source.index("source_frame_count = int(props.shape[0])"), source.index("model, device, detector = _load_runtime()"))


if __name__ == "__main__":
    unittest.main()


class GenDIntegrationSourceTests(unittest.TestCase):
    def test_api_uses_worker_and_verifies_upload_hash(self):
        client = Path("backend/gend_client.py").read_text()
        self.assertIn("modal.Function.from_name(GEND_APP_NAME, GEND_FUNCTION_NAME)", client)
        self.assertIn("hashlib.sha256(video_bytes).hexdigest()", client)
        self.assertIn("source_video_sha256", client)

    def test_api_keeps_verdict_not_assessed_after_model_scores(self):
        source = Path("backend/app.py").read_text()
        self.assertIn('"classification_status"] = "not_assessed"', source)
        self.assertIn('"scores_available_uncalibrated"', source)
        self.assertIn("await asyncio.to_thread(invoke_gend_inference, raw, filename)", source)

    def test_stream_preserves_intake_if_worker_fails(self):
        source = Path("backend/app.py").read_text()
        self.assertIn('"GenD isolated worker"', source)
        self.assertIn('"worker_unavailable"', source)
        self.assertIn("intake evidence is preserved", source)

    def test_intake_worker_stages_are_pending_before_remote_inference(self):
        source = Path("backend/video_forensics.py").read_text()
        self.assertIn('"GenD model inference", "pending"', source)
        self.assertIn('"GenD input gate", "pending"', source)


if __name__ == "__main__":
    unittest.main()
