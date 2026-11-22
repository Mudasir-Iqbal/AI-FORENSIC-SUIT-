"""Run a real video through the deployed isolated GenD Modal function.

Usage:
    python -m pip install modal
    modal setup
    python backend/run_gend_inference_test.py path/to/video.mp4

This sends the video bytes to the already-deployed worker. It does not deploy code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import modal

APP_NAME = "deepguard-gend"
MAX_VIDEO_BYTES = 250 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def validate_result(result: dict[str, Any], expected_sha256: str) -> None:
    if result.get("source_video_sha256") != expected_sha256:
        raise RuntimeError("Worker source-video SHA-256 does not match the uploaded file.")

    status = result.get("status")
    if status != "official_preprocessing_and_inference_complete":
        raise RuntimeError(
            "GenD did not complete inference. Worker response: "
            + json.dumps(result, ensure_ascii=False)
        )

    frames = result.get("frame_evidence")
    if not isinstance(frames, list):
        raise RuntimeError("Worker did not return per-frame evidence.")
    if not 8 <= len(frames) <= 32 or len(frames) != result.get("detected_face_frames"):
        raise RuntimeError("Detected face-frame count is outside the expected 8-32 range.")

    probabilities = result.get("video_class_probabilities")
    if not isinstance(probabilities, dict) or not {"real", "fake"} <= probabilities.keys():
        raise RuntimeError("Worker did not return both video class probabilities.")
    real_probability = float(probabilities["real"])
    fake_probability = float(probabilities["fake"])
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in (real_probability, fake_probability)):
        raise RuntimeError("Worker returned invalid video probabilities.")
    if not math.isclose(real_probability + fake_probability, 1.0, rel_tol=0.0, abs_tol=2e-5):
        raise RuntimeError("Video class probabilities do not sum to approximately 1.")

    for index, frame in enumerate(frames):
        logits = frame.get("genD_logits")
        frame_probs = frame.get("class_probabilities")
        crop_hash = frame.get("aligned_crop_sha256", "")
        if not isinstance(logits, list) or len(logits) != 2:
            raise RuntimeError(f"Frame {index} has invalid GenD logits.")
        if not isinstance(frame_probs, dict) or not {"real_class_0", "fake_class_1"} <= frame_probs.keys():
            raise RuntimeError(f"Frame {index} has incomplete class probabilities.")
        if len(crop_hash) != 64:
            raise RuntimeError(f"Frame {index} has no valid aligned-crop SHA-256.")
        numeric_values = [float(value) for value in logits]
        numeric_values.extend(float(frame_probs[key]) for key in ("real_class_0", "fake_class_1"))
        if not all(math.isfinite(value) for value in numeric_values):
            raise RuntimeError(f"Frame {index} contains non-finite model outputs.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test real inference on the deployed GenD worker.")
    parser.add_argument("video", type=Path, help="Local video file to submit to Modal.")
    args = parser.parse_args()

    path = args.video.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"Video file does not exist: {path}")
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise SystemExit("Unsupported extension. Use MP4, MOV, MKV, AVI, WEBM, or M4V.")

    video_bytes = path.read_bytes()
    if not video_bytes:
        raise SystemExit("Video file is empty.")
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise SystemExit("Video exceeds the worker's 250 MB limit.")

    expected_sha256 = hashlib.sha256(video_bytes).hexdigest()
    print(f"Submitting {path.name} ({len(video_bytes)} bytes)")
    print(f"Local SHA-256: {expected_sha256}")

    worker = modal.Function.from_name(APP_NAME, "infer_video")
    result = worker.remote(video_bytes, path.name)
    validate_result(result, expected_sha256)

    print("\nGEN D INFERENCE SMOKE TEST: PASS")
    print(json.dumps({
        "status": result["status"],
        "model_id": result.get("model_id"),
        "model_revision": result.get("model_revision"),
        "device": result.get("device"),
        "source_frame_count": result.get("source_frame_count"),
        "detected_face_frames": result.get("detected_face_frames"),
        "video_class_probabilities": result.get("video_class_probabilities"),
        "processing_time_ms": result.get("processing_time_ms"),
        "source_video_sha256": result.get("source_video_sha256"),
        "verdict_status": result.get("verdict_status"),
        "license_notice": result.get("research_only_detector_weight_license"),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
