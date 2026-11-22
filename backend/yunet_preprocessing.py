"""Experimental YuNet face detection using the MIT-licensed OpenCV Zoo model.

YuNet candidates are NOT declared GenD-equivalent. They are retained for
side-by-side detector and crop validation only.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import cv2
import numpy as np

MODEL_PATH = Path(os.getenv("YUNET_MODEL_PATH", "/opt/models/face_detection_yunet_2023mar.onnx"))
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_SOURCE = (
    "https://github.com/opencv/opencv_zoo/tree/"
    "d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/face_detection_yunet"
)
DETECTION_THRESHOLD = 0.5
NMS_THRESHOLD = 0.3
MAX_DETECTION_DIMENSION = 1280


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _align_face(
    image_bgr: np.ndarray,
    landmarks: np.ndarray,
    target_size: tuple[int, int] = (256, 256),
    scale: float = 1.3,
) -> np.ndarray:
    """Use GenD detector.py's published five-point alignment geometry."""
    dst = np.array(
        [[0.34, 0.46], [0.66, 0.46], [0.50, 0.64], [0.37, 0.82], [0.63, 0.82]],
        dtype=np.float32,
    )
    width, height = target_size
    dst[:, 0] *= width
    dst[:, 1] *= height
    margin_rate = scale - 1.0
    x_margin = width * margin_rate / 2.0
    y_margin = height * margin_rate / 2.0
    dst[:, 0] += x_margin
    dst[:, 1] += y_margin
    dst[:, 0] *= width / (width + 2.0 * x_margin)
    dst[:, 1] *= height / (height + 2.0 * y_margin)

    transform, _ = cv2.estimateAffinePartial2D(
        landmarks.astype(np.float32), dst, method=cv2.LMEDS
    )
    if transform is None or not np.isfinite(transform).all():
        raise ValueError("Five-point similarity transform could not be estimated.")
    return cv2.warpAffine(
        image_bgr, transform, target_size, flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
    )


def screen_and_align_yunet_frames(
    frame_paths: list[Path],
    output_dir: Path,
    sample_interval_seconds: float,
) -> dict[str, Any]:
    """Create temporary YuNet candidate crops from sampled source frames."""
    if not MODEL_PATH.is_file():
        return {
            "status": "unavailable",
            "detector": "OpenCV Zoo YuNet",
            "detector_license": "MIT",
            "model_path_configured": False,
            "detected_frames": 0,
            "aligned_frames": 0,
            "total_frames": len(frame_paths),
            "genD_compatibility": "not_validated",
            "warning": f"YuNet model file is missing at {MODEL_PATH}.",
            "frames": [],
        }

    model_sha256 = _sha256(MODEL_PATH)
    if model_sha256 != MODEL_SHA256:
        return {
            "status": "blocked",
            "detector": "OpenCV Zoo YuNet",
            "detector_license": "MIT",
            "model_path_configured": True,
            "model_sha256": model_sha256,
            "detected_frames": 0,
            "aligned_frames": 0,
            "total_frames": len(frame_paths),
            "genD_compatibility": "not_validated",
            "warning": "YuNet model SHA-256 does not match the pinned OpenCV Zoo artifact.",
            "frames": [],
        }

    if not hasattr(cv2, "FaceDetectorYN_create"):
        return {
            "status": "unavailable",
            "detector": "OpenCV Zoo YuNet",
            "detector_license": "MIT",
            "model_path_configured": True,
            "model_sha256": model_sha256,
            "detected_frames": 0,
            "aligned_frames": 0,
            "total_frames": len(frame_paths),
            "genD_compatibility": "not_validated",
            "warning": "Installed OpenCV build does not expose FaceDetectorYN_create.",
            "frames": [],
        }

    output_dir.mkdir(parents=True, exist_ok=True)
    detector = cv2.FaceDetectorYN_create(
        str(MODEL_PATH), "", (320, 320),
        DETECTION_THRESHOLD, NMS_THRESHOLD, 5000,
    )
    frame_results: list[dict[str, Any]] = []
    detected_count = 0
    aligned_count = 0

    for index, frame_path in enumerate(frame_paths):
        result: dict[str, Any] = {
            "sample_index": index,
            "timestamp_seconds": round(index * sample_interval_seconds, 3),
            "status": "no_face_detected",
            "face_count": 0,
            "detection_confidence": None,
            "aligned_crop_sha256": None,
            "aligned_crop_size": None,
        }
        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if image is None:
            result["status"] = "frame_decode_failed"
            frame_results.append(result)
            continue

        original_height, original_width = image.shape[:2]
        resize_scale = min(1.0, MAX_DETECTION_DIMENSION / max(original_width, original_height))
        if resize_scale < 1.0:
            detection_image = cv2.resize(
                image,
                (max(1, round(original_width * resize_scale)),
                 max(1, round(original_height * resize_scale))),
                interpolation=cv2.INTER_AREA,
            )
        else:
            detection_image = image

        detector.setInputSize((detection_image.shape[1], detection_image.shape[0]))
        _, faces = detector.detect(detection_image)
        if faces is None or len(faces) == 0:
            frame_results.append(result)
            continue

        detected_count += 1
        # YuNet rows: x, y, w, h, five (x,y) landmarks, confidence.
        largest = max(faces, key=lambda face: max(0.0, face[2]) * max(0.0, face[3]))
        face_scale_x = original_width / detection_image.shape[1]
        face_scale_y = original_height / detection_image.shape[0]
        points = largest[4:14].reshape(5, 2).astype(np.float32)
        points[:, 0] *= face_scale_x
        points[:, 1] *= face_scale_y

        # OpenCV YuNet order is right eye, left eye, nose, right mouth, left mouth.
        # Sort eye and mouth pairs geometrically to match GenD's left-to-right layout.
        eye_points = sorted(points[:2].tolist(), key=lambda point: point[0])
        mouth_points = sorted(points[3:5].tolist(), key=lambda point: point[0])
        five_points = np.asarray(eye_points + [points[2].tolist()] + mouth_points, dtype=np.float32)
        box_x = float(largest[0]) * face_scale_x
        box_y = float(largest[1]) * face_scale_y
        box_w = float(largest[2]) * face_scale_x
        box_h = float(largest[3]) * face_scale_y
        face_bbox = [
            round(max(0.0, min(float(original_width), box_x)), 3),
            round(max(0.0, min(float(original_height), box_y)), 3),
            round(max(0.0, min(float(original_width), box_x + box_w)), 3),
            round(max(0.0, min(float(original_height), box_y + box_h)), 3),
        ]
        result.update({
            "bounding_box_xyxy": face_bbox,
            "bounding_box_source": "yunet_detector",
            "landmarks_5_xy": np.round(five_points, 3).tolist(),
            "landmark_order": ["left_eye", "right_eye", "nose", "left_mouth", "right_mouth"],
            "coordinate_space": "source_frame_pixels",
        })

        try:
            aligned = _align_face(image, five_points, (256, 256), 1.3)
            crop_path = output_dir / f"yunet_aligned_{index:04d}.png"
            if not cv2.imwrite(str(crop_path), aligned):
                raise ValueError("Aligned YuNet crop could not be written.")
            crop_hash = _sha256(crop_path)
            result.update({
                "status": "experimental_aligned",
                "face_count": int(len(faces)),
                "detection_confidence": round(float(largest[14]), 5),
                "aligned_crop_sha256": crop_hash,
                "aligned_crop_size": [256, 256],
                "detector_frame_size": [int(detection_image.shape[1]), int(detection_image.shape[0])],
                "crop_source_size": [original_width, original_height],
            })
            aligned_count += 1
        except Exception as exc:
            result.update({
                "status": "alignment_failed",
                "face_count": int(len(faces)),
                "detail": str(exc)[:240],
            })
        frame_results.append(result)

    return {
        "status": "experimental_complete",
        "detector": "OpenCV Zoo YuNet",
        "detector_version": cv2.__version__,
        "detector_license": "MIT",
        "model_source": MODEL_SOURCE,
        "model_sha256": model_sha256,
        "detection_threshold": DETECTION_THRESHOLD,
        "nms_threshold": NMS_THRESHOLD,
        "max_detection_dimension": MAX_DETECTION_DIMENSION,
        "detected_frames": detected_count,
        "aligned_frames": aligned_count,
        "total_frames": len(frame_paths),
        "crop_size": [256, 256],
        "context_scale": 1.3,
        "alignment_geometry": "GenD detector.py five-point similarity transform",
        "genD_compatibility": "not_validated",
        "warning": (
            "YuNet is a separately licensed detector, not GenD's upstream SCRFD/RetinaFace. "
            "The five-point geometry is matched, but detector parity and crop equivalence "
            "have not been benchmarked. These crops must not be passed to GenD yet."
        ),
        "frames": frame_results,
    }
