"""Experimental MediaPipe face screening and GenD-style five-point alignment.

This is deliberately NOT declared equivalent to GenD's upstream SCRFD/RetinaFace
detector. It creates temporary candidate crops for preprocessing validation only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np


FACE_LANDMARK_INDICES = {
    "eye_a": 33,
    "eye_b": 263,
    "nose_tip": 1,
    "mouth_a": 61,
    "mouth_b": 291,
}


def _align_face(
    image_bgr: np.ndarray,
    landmarks: np.ndarray,
    target_size: tuple[int, int] = (256, 256),
    scale: float = 1.3,
) -> np.ndarray:
    """Mirror the published GenD detector.py five-point alignment geometry."""
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


def screen_and_align_frames(
    frame_paths: list[Path],
    output_dir: Path,
    sample_interval_seconds: float,
    max_faces: int = 5,
) -> dict[str, Any]:
    """Detect faces and create hashed temporary 256x256 candidate crops."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_results: list[dict[str, Any]] = []
    detected_count = 0
    aligned_count = 0

    with mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=max_faces,
        refine_landmarks=False,
        min_detection_confidence=0.5,
    ) as detector:
        for index, frame_path in enumerate(frame_paths):
            result: dict[str, Any] = {
                "sample_index": index,
                "timestamp_seconds": round(index * sample_interval_seconds, 3),
                "status": "no_face_detected",
                "face_count": 0,
                "aligned_crop_sha256": None,
                "aligned_crop_size": None,
            }
            image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
            if image is None:
                result["status"] = "frame_decode_failed"
                frame_results.append(result)
                continue

            height, width = image.shape[:2]
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            detection = detector.process(rgb)
            faces = detection.multi_face_landmarks or []
            result["face_count"] = len(faces)
            if not faces:
                frame_results.append(result)
                continue

            detected_count += 1
            # Select the largest detected face, matching GenD's largest-face policy.
            def face_area(face: Any) -> float:
                xs = [point.x for point in face.landmark]
                ys = [point.y for point in face.landmark]
                return max(0.0, max(xs) - min(xs)) * max(0.0, max(ys) - min(ys))

            selected = max(faces, key=face_area)
            points = selected.landmark
            eye_points = sorted(
                [
                    [points[FACE_LANDMARK_INDICES["eye_a"]].x * width,
                     points[FACE_LANDMARK_INDICES["eye_a"]].y * height],
                    [points[FACE_LANDMARK_INDICES["eye_b"]].x * width,
                     points[FACE_LANDMARK_INDICES["eye_b"]].y * height],
                ],
                key=lambda point: point[0],
            )
            mouth_points = sorted(
                [
                    [points[FACE_LANDMARK_INDICES["mouth_a"]].x * width,
                     points[FACE_LANDMARK_INDICES["mouth_a"]].y * height],
                    [points[FACE_LANDMARK_INDICES["mouth_b"]].x * width,
                     points[FACE_LANDMARK_INDICES["mouth_b"]].y * height],
                ],
                key=lambda point: point[0],
            )
            nose = points[FACE_LANDMARK_INDICES["nose_tip"]]
            five_points = np.asarray(
                eye_points
                + [[nose.x * width, nose.y * height]]
                + mouth_points,
                dtype=np.float32,
            )
            mesh_xy = np.asarray(
                [[point.x * width, point.y * height] for point in points],
                dtype=np.float32,
            )
            mesh_bbox = [
                round(max(0.0, float(mesh_xy[:, 0].min())), 3),
                round(max(0.0, float(mesh_xy[:, 1].min())), 3),
                round(min(float(width), float(mesh_xy[:, 0].max())), 3),
                round(min(float(height), float(mesh_xy[:, 1].max())), 3),
            ]
            result.update({
                "bounding_box_xyxy": mesh_bbox,
                "bounding_box_source": "mediapipe_mesh_extent_not_detector_box",
                "landmarks_5_xy": np.round(five_points, 3).tolist(),
                "landmark_order": ["left_eye", "right_eye", "nose", "left_mouth", "right_mouth"],
                "coordinate_space": "source_frame_pixels",
            })

            try:
                aligned = _align_face(image, five_points, (256, 256), 1.3)
                crop_path = output_dir / f"aligned_{index:04d}.png"
                if not cv2.imwrite(str(crop_path), aligned):
                    raise ValueError("Aligned crop could not be written.")
                crop_bytes = crop_path.read_bytes()
                result.update(
                    {
                        "status": "experimental_aligned",
                        "aligned_crop_sha256": hashlib.sha256(crop_bytes).hexdigest(),
                        "aligned_crop_size": [256, 256],
                    }
                )
                aligned_count += 1
            except Exception as exc:
                result["status"] = "alignment_failed"
                result["detail"] = str(exc)[:240]
            frame_results.append(result)

    return {
        "status": "experimental_complete",
        "detector": "MediaPipe Face Mesh",
        "detector_version": getattr(mp, "__version__", "unknown"),
        "detector_license": "Apache-2.0",
        "landmark_mapping": FACE_LANDMARK_INDICES,
        "detected_frames": detected_count,
        "aligned_frames": aligned_count,
        "total_frames": len(frame_paths),
        "crop_size": [256, 256],
        "context_scale": 1.3,
        "crop_format": "PNG",
        "temporary_crops_deleted_after_request": True,
        "genD_compatibility": "not_validated",
        "warning": (
            "Experimental MediaPipe landmarks are not the official GenD SCRFD/RetinaFace "
            "detector output. These crops must not be passed to GenD until equivalence "
            "and preprocessing compatibility are validated."
        ),
        "frames": frame_results,
    }
