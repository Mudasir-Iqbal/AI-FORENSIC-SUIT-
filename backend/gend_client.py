"""Safe client for the separately deployed GenD Modal inference worker."""
from __future__ import annotations
import hashlib
import math
import os
from typing import Any

GEND_APP_NAME = os.getenv("GEND_MODAL_APP_NAME", "deepguard-gend")
GEND_FUNCTION_NAME = "infer_video"
GEND_MODEL_ID = "yermandy/GenD_CLIP_L_14"
GEND_MODEL_REVISION = "9413725434bfe93ef069b7b4dcdf817cd83529b3"


def _validate_worker_result(result: Any, expected_sha256: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise RuntimeError("GenD worker returned a non-object response.")
    if result.get("source_video_sha256") != expected_sha256:
        raise RuntimeError("GenD worker source-video SHA-256 does not match the submitted upload.")
    if result.get("status") != "official_preprocessing_and_inference_complete":
        if result.get("verdict_status") == "not_assessed":
            return result
        raise RuntimeError(f"GenD worker returned an unexpected status: {result.get('status')!r}.")
    if result.get("model_id") != GEND_MODEL_ID or result.get("model_revision") != GEND_MODEL_REVISION:
        raise RuntimeError("GenD worker model identity or pinned revision does not match the expected artifact.")
    frames = result.get("frame_evidence")
    if not isinstance(frames, list) or not 8 <= len(frames) <= 32 or len(frames) != result.get("detected_face_frames"):
        raise RuntimeError("GenD worker returned an invalid face-frame evidence count.")
    scores = result.get("video_class_probabilities")
    if not isinstance(scores, dict) or not {"real", "fake"} <= scores.keys():
        raise RuntimeError("GenD worker did not return both video class probabilities.")
    values = [float(scores["real"]), float(scores["fake"])]
    if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in values) or not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=2e-5):
        raise RuntimeError("GenD worker returned invalid or unnormalized video probabilities.")
    for index, frame in enumerate(frames):
        logits, frame_scores = frame.get("genD_logits"), frame.get("class_probabilities")
        if not isinstance(logits, list) or len(logits) != 2 or len(frame.get("aligned_crop_sha256", "")) != 64:
            raise RuntimeError(f"GenD frame evidence {index} is incomplete.")
        if not isinstance(frame_scores, dict) or not {"real_class_0", "fake_class_1"} <= frame_scores.keys():
            raise RuntimeError(f"GenD frame evidence {index} has incomplete class probabilities.")
        numeric = [float(v) for v in logits]
        numeric.extend(float(frame_scores[k]) for k in ("real_class_0", "fake_class_1"))
        if not all(math.isfinite(v) for v in numeric):
            raise RuntimeError(f"GenD frame evidence {index} contains non-finite values.")
    return result


def invoke_gend_inference(video_bytes: bytes, filename: str) -> dict[str, Any]:
    """Call the deployed Modal function and bind its response to the exact upload."""
    if not video_bytes:
        raise ValueError("Uploaded video is empty.")
    expected_sha256 = hashlib.sha256(video_bytes).hexdigest()
    import modal
    worker = modal.Function.from_name(GEND_APP_NAME, GEND_FUNCTION_NAME)
    return _validate_worker_result(worker.remote(video_bytes, filename), expected_sha256)
