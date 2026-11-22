import unittest

from backend.detector_parity_benchmark import BenchmarkInputError, benchmark


class DetectorParityBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "schema_version": 1,
            "reference_detector": "gend_official_scrfd",
            "candidate_detector": "opencv_yunet",
            "coordinate_space": "source_frame_pixels",
            "frames": [{
                "frame_id": "frame-0001",
                "width": 1920,
                "height": 1080,
                "reference_faces": [{
                    "bbox": [100, 100, 300, 300],
                    "landmarks": [[150, 170], [250, 170], [200, 210], [165, 250], [235, 250]],
                }],
                "candidate_faces": [{
                    "bbox": [100, 100, 300, 300],
                    "landmarks": [[150, 170], [250, 170], [200, 210], [165, 250], [235, 250]],
                }],
            }],
        }

    def test_identical_detections_match_perfectly_but_never_auto_certify(self):
        result = benchmark(self.payload)
        self.assertEqual(result["matched_face_count"], 1)
        self.assertEqual(result["detection_precision"], 1.0)
        self.assertEqual(result["detection_recall"], 1.0)
        self.assertEqual(result["mean_matched_iou"], 1.0)
        self.assertEqual(result["mean_normalized_landmark_rmse"], 0.0)
        self.assertEqual(result["compatibility_verdict"], "not_validated")

    def test_missing_candidate_is_counted_as_miss(self):
        self.payload["frames"][0]["candidate_faces"] = []
        result = benchmark(self.payload)
        self.assertEqual(result["missed_reference_face_count"], 1)
        self.assertEqual(result["detection_recall"], 0.0)

    def test_invalid_landmark_count_is_rejected(self):
        self.payload["frames"][0]["candidate_faces"][0]["landmarks"] = [[1, 2]]
        with self.assertRaises(BenchmarkInputError):
            benchmark(self.payload)

    def test_duplicate_frame_ids_are_rejected(self):
        self.payload["frames"].append(dict(self.payload["frames"][0]))
        with self.assertRaises(BenchmarkInputError):
            benchmark(self.payload)


if __name__ == "__main__":
    unittest.main()
