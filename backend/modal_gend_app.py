"""Isolated official GenD video inference worker.

Reproduces the upstream WACV 2026 detector.py path. InsightFace detector weights
are restricted to non-commercial research use; this worker is research-only.
"""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import modal

APP_NAME = "deepguard-gend"
MODEL_ID = "yermandy/GenD_CLIP_L_14"
MODEL_REVISION = "9413725434bfe93ef069b7b4dcdf817cd83529b3"
MODEL_SHA256 = "d76f0bdfd74a29fe1b1c1b84a80ac92486993e426878e8c7a3944281fbb96833"
DETECTOR_REPO_COMMIT = "387a42266dd385fbe8f7626c5d3aa03eea3bfaab"
DETECTOR_MODEL_SHA256 = "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91"
DETECTOR_MODEL_URL = (
    "https://huggingface.co/datasets/theanhntp/Liblib/resolve/"
    "ae4357741af379482690fe3e0f2fa6fd32ba33b4/"
    "insightface/models/buffalo_l/det_10g.onnx"
)
MAX_VIDEO_BYTES = 250 * 1024 * 1024
MAX_SOURCE_FRAMES = 1800
TARGET_FACE_FRAMES = 32
MIN_FACE_FRAMES_FOR_ASSESSMENT = 8
INFERENCE_BATCH_SIZE = 8
DETECTOR_THRESHOLD = 0.1
NMS_THRESHOLD = 0.4
DETECTOR_INPUT_SIZE = (640, 640)
ALIGNMENT_SCALE = 1.3

app = modal.App(APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg")
    .pip_install(
        "torch==2.8.0",
        "torchvision==0.23.0",
        "transformers==4.56.2",
        "safetensors==0.6.2",
        "Pillow==11.3.0",
        "huggingface_hub==0.34.4",
        "numpy==2.1.3",
        "opencv-python-headless==4.12.0.88",
        "onnxruntime==1.21.0",
        "imageio==2.37.0",
        "av==16.1.0",
        "tqdm==4.67.1",
    )
    .run_commands(
        "git clone https://github.com/yermandy/GenD.git /opt/GenD",
        f"cd /opt/GenD && git checkout {DETECTOR_REPO_COMMIT}",
        "mkdir -p /opt/GenD/weights/models/buffalo_l",
        f"curl -fL '{DETECTOR_MODEL_URL}' -o /opt/GenD/weights/models/buffalo_l/det_10g.onnx",
        f"echo '{DETECTOR_MODEL_SHA256}  /opt/GenD/weights/models/buffalo_l/det_10g.onnx' | sha256sum -c -",
    )
    .env({"PYTHONPATH": "/opt/GenD"})
)

_model = None
_device = None
_detector = None


def _load_runtime():
    global _model, _device, _detector
    if _model is not None and _detector is not None:
        return _model, _device, _detector

    import sys
    sys.path.insert(0, "/opt/GenD")
    import torch
    from huggingface_hub import hf_hub_download
    from src.hf.modeling_gend import GenD
    from detector import prepare_model

    checkpoint_path = hf_hub_download(
        repo_id=MODEL_ID, filename="model.safetensors", revision=MODEL_REVISION
    )
    digest = hashlib.sha256()
    with open(checkpoint_path, "rb") as checkpoint:
        for chunk in iter(lambda: checkpoint.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise RuntimeError("GenD checkpoint SHA-256 does not match the pinned artifact.")

    os.chdir("/opt/GenD")
    detector_path = Path("weights/models/buffalo_l/det_10g.onnx")
    detector_digest = hashlib.sha256(detector_path.read_bytes()).hexdigest()
    if detector_digest != DETECTOR_MODEL_SHA256:
        raise RuntimeError("Official RetinaFace detector weight SHA-256 mismatch.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GenD.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model.to(device)
    model.eval()

    # This is the exact detector factory from the pinned official GenD repository:
    # 640x640, detector threshold 0.1, NMS 0.4.
    detector = prepare_model(det_thres=DETECTOR_THRESHOLD, nms_thresh=NMS_THRESHOLD)

    _model, _device, _detector = model, device, detector
    return _model, _device, _detector


@app.function(image=image, cpu=8, memory=16384, timeout=900, scaledown_window=300)
def infer_video(video_bytes: bytes, filename: str = "input.mp4") -> dict[str, Any]:
    """Run the official GenD face detector, alignment, CLIP preprocessing and model.

    Returns frame and mean video probabilities. A binary verdict remains withheld
    until an independent validation set establishes a deployment threshold.
    """
    if not video_bytes:
        raise ValueError("Uploaded video is empty.")
    if len(video_bytes) > MAX_VIDEO_BYTES:
        raise ValueError("Video exceeds the 250 MB GenD worker limit.")

    import imageio.v3 as iio
    import numpy as np
    import torch
    import cv2
    from PIL import Image
    from detector import get_video_frames_generator, align_face

    started = time.perf_counter()
    model, device, detector = _load_runtime()

    with tempfile.TemporaryDirectory(prefix="deepguard-gend-") as temp_dir:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}:
            suffix = ".mp4"
        video_path = Path(temp_dir) / ("source" + suffix)
        video_path.write_bytes(video_bytes)

        try:
            props = iio.improps(str(video_path), plugin="pyav")
            source_frame_count = int(props.shape[0])
        except Exception as exc:
            raise ValueError("GenD could not decode the uploaded video with the official PyAV path.") from exc

        if source_frame_count < TARGET_FACE_FRAMES:
            return {
                "status": "insufficient_source_frames",
                "verdict_status": "not_assessed",
                "model_id": MODEL_ID,
                "source_frame_count": source_frame_count,
                "required_target_face_frames": TARGET_FACE_FRAMES,
                "reason": "Official GenD at_least sampling requires enough source frames to search for 32 face frames.",
            }
        if source_frame_count > MAX_SOURCE_FRAMES:
            raise ValueError(
                f"Video has {source_frame_count} frames; the research worker limit is {MAX_SOURCE_FRAMES} source frames."
            )

        # The official detector.py uses max-spread frame ordering in at_least mode,
        # then stops after 32 successfully detected/aligned faces.
        frame_generator = get_video_frames_generator(
            str(video_path),
            mask_path=None,
            stride=1,
            num_frames=TARGET_FACE_FRAMES,
            mode="at_least",
        )

        tensors = []
        frame_evidence = []
        for frame, frame_id, _ in frame_generator:
            boxes, landmarks = detector.detect(frame)
            if len(boxes) == 0:
                continue

            # Official detector.py selects the largest detected face.
            areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            selected_index = int(np.argmax(areas))
            selected_box = boxes[selected_index]
            selected_landmarks = landmarks[selected_index]
            aligned_bgr, _ = align_face(
                frame,
                selected_landmarks,
                target_size=None,
                scale=ALIGNMENT_SCALE,
            )
            if aligned_bgr is None or aligned_bgr.size == 0:
                continue

            aligned_rgb = cv2.cvtColor(aligned_bgr, cv2.COLOR_BGR2RGB)
            aligned_image = Image.fromarray(aligned_rgb)
            # Official CLIP processor performs the model's resize/normalization.
            tensor = model.feature_extractor.preprocess(aligned_image)
            tensors.append(tensor)

            crop_buffer = io.BytesIO()
            aligned_image.save(crop_buffer, format="PNG")
            crop_bytes = crop_buffer.getvalue()
            frame_evidence.append({
                "source_frame_index": int(frame_id),
                "face_detection_confidence": round(float(selected_box[4]), 6),
                "face_bbox_xyxy": [round(float(v), 3) for v in selected_box[:4]],
                "five_landmarks_xy": [
                    [round(float(x), 3), round(float(y), 3)]
                    for x, y in selected_landmarks.tolist()
                ],
                "aligned_crop_width": int(aligned_image.width),
                "aligned_crop_height": int(aligned_image.height),
                "aligned_crop_sha256": hashlib.sha256(crop_bytes).hexdigest(),
                "alignment": "official_GenD_align_face_target_size_none_scale_1.3",
            })
            if len(tensors) >= TARGET_FACE_FRAMES:
                break

        if len(tensors) < MIN_FACE_FRAMES_FOR_ASSESSMENT:
            return {
                "status": "insufficient_detected_faces",
                "verdict_status": "not_assessed",
                "model_id": MODEL_ID,
                "source_frame_count": source_frame_count,
                "detected_face_frames": len(tensors),
                "minimum_face_frames_for_assessment": MIN_FACE_FRAMES_FOR_ASSESSMENT,
                "target_face_frames": TARGET_FACE_FRAMES,
                "frame_evidence": frame_evidence,
                "reason": "Too few valid face crops were found; no authenticity score is issued.",
            }

        logits_parts = []
        with torch.inference_mode():
            for offset in range(0, len(tensors), INFERENCE_BATCH_SIZE):
                batch = torch.stack(tensors[offset:offset + INFERENCE_BATCH_SIZE]).to(device)
                logits = model(batch)
                if logits.ndim != 2 or logits.shape != (batch.shape[0], 2):
                    raise RuntimeError(f"Unexpected GenD logits shape: {tuple(logits.shape)}")
                if not torch.isfinite(logits).all():
                    raise RuntimeError("GenD returned non-finite logits.")
                logits_parts.append(logits.float().cpu())

        frame_logits = torch.cat(logits_parts, dim=0)
        frame_probabilities = torch.softmax(frame_logits, dim=-1).numpy()
        # Official dataset labels: class 0 = real, class 1 = fake.
        # Official video evaluation aggregates per-frame probabilities by mean.
        mean_probabilities = frame_probabilities.mean(axis=0)
        elapsed_ms = round((time.perf_counter() - started) * 1000)

        for index, evidence in enumerate(frame_evidence):
            evidence["genD_logits"] = [round(float(v), 7) for v in frame_logits[index].tolist()]
            evidence["class_probabilities"] = {
                "real_class_0": round(float(frame_probabilities[index, 0]), 7),
                "fake_class_1": round(float(frame_probabilities[index, 1]), 7),
            }

        return {
            "status": "official_preprocessing_and_inference_complete",
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "model_checkpoint_sha256_verified": MODEL_SHA256,
            "official_detector_repo_commit": DETECTOR_REPO_COMMIT,
            "detector_model_sha256_verified": DETECTOR_MODEL_SHA256,
            "detector": "GenD upstream RetinaFace / det_10g.onnx",
            "detector_threshold": DETECTOR_THRESHOLD,
            "nms_threshold": NMS_THRESHOLD,
            "detector_input_size": list(DETECTOR_INPUT_SIZE),
            "frame_sampling": "official_at_least_max_spread_until_32_successful_face_frames",
            "target_face_frames": TARGET_FACE_FRAMES,
            "detected_face_frames": len(frame_evidence),
            "alignment": {"method": "official_five_landmark_similarity", "scale": ALIGNMENT_SCALE, "target_size": None},
            "model_preprocessing": "official_GenD_CLIPProcessor_preprocess",
            "class_mapping": {"class_0": "real", "class_1": "fake"},
            "frame_aggregation": "arithmetic_mean_of_per_frame_softmax_probabilities",
            "video_class_probabilities": {
                "real": round(float(mean_probabilities[0]), 7),
                "fake": round(float(mean_probabilities[1]), 7),
            },
            "verdict_status": "not_assessed_threshold_requires_independent_validation",
            "device": str(device),
            "processing_time_ms": elapsed_ms,
            "frame_evidence": frame_evidence,
            "research_only_detector_weight_license": "InsightFace public pretrained weights are restricted to non-commercial research use.",
            "warning": "Scores are model outputs, not calibrated forensic certainty or proof of authenticity. Validate threshold and cross-dataset performance before operational use.",
        }


@app.function(image=image, cpu=8, memory=16384, timeout=900, scaledown_window=300)
def health() -> dict[str, str]:
    model, device, detector = _load_runtime()
    return {
        "service": APP_NAME,
        "status": "model_and_official_detector_loaded",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_checkpoint_sha256_verified": MODEL_SHA256,
        "official_detector_repo_commit": DETECTOR_REPO_COMMIT,
        "detector_model_sha256_verified": DETECTOR_MODEL_SHA256,
        "detector": type(detector).__name__,
        "device": str(device),
        "model_class": type(model).__name__,
        "license_scope": "non-commercial research only for InsightFace pretrained detector weights",
    }
