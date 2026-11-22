"""Offline detector-parity benchmark for GenD preprocessing candidates.

Input JSON contains per-frame face detections from a reference detector and a
candidate detector. The reference should be the official GenD SCRFD/RetinaFace
pipeline when its weights and use are authorized.

This tool reports measurements only. It never marks a detector GenD-compatible:
that decision also requires protocol review, representative datasets, and
independent validation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


class BenchmarkInputError(ValueError):
    """Raised when a benchmark file is malformed or ambiguous."""


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BenchmarkInputError(f"{field} must be a number.")
    result = float(value)
    if not math.isfinite(result):
        raise BenchmarkInputError(f"{field} must be finite.")
    return result


def _bbox(face: dict[str, Any], field: str) -> tuple[float, float, float, float]:
    values = face.get("bbox")
    if not isinstance(values, list) or len(values) != 4:
        raise BenchmarkInputError(f"{field}.bbox must be [x1, y1, x2, y2].")
    x1, y1, x2, y2 = (_number(v, f"{field}.bbox") for v in values)
    if x2 <= x1 or y2 <= y1:
        raise BenchmarkInputError(f"{field}.bbox must have positive area.")
    return x1, y1, x2, y2


def _landmarks(face: dict[str, Any], field: str) -> list[tuple[float, float]] | None:
    values = face.get("landmarks")
    if values is None:
        return None
    if not isinstance(values, list) or len(values) != 5:
        raise BenchmarkInputError(f"{field}.landmarks must contain exactly five [x, y] points.")
    points: list[tuple[float, float]] = []
    for index, point in enumerate(values):
        if not isinstance(point, list) or len(point) != 2:
            raise BenchmarkInputError(f"{field}.landmarks[{index}] must be [x, y].")
        points.append((_number(point[0], field), _number(point[1], field)))
    return points


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _normalized_landmark_rmse(
    reference: list[tuple[float, float]],
    candidate: list[tuple[float, float]],
    reference_bbox: tuple[float, float, float, float],
) -> float:
    squared = [
        (rx - cx) ** 2 + (ry - cy) ** 2
        for (rx, ry), (cx, cy) in zip(reference, candidate)
    ]
    diagonal = math.hypot(
        reference_bbox[2] - reference_bbox[0],
        reference_bbox[3] - reference_bbox[1],
    )
    return math.sqrt(sum(squared) / len(squared)) / diagonal if diagonal else 0.0


def _validate_faces(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise BenchmarkInputError(f"{field} must be a list.")
    faces = []
    for index, face in enumerate(value):
        name = f"{field}[{index}]"
        if not isinstance(face, dict):
            raise BenchmarkInputError(f"{name} must be an object.")
        faces.append({
            "bbox": _bbox(face, name),
            "landmarks": _landmarks(face, name),
        })
    return faces


def _match_faces(
    reference: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    iou_threshold: float,
) -> list[tuple[int, int, float]]:
    pairs = []
    for ref_index, ref_face in enumerate(reference):
        for cand_index, cand_face in enumerate(candidate):
            overlap = _iou(ref_face["bbox"], cand_face["bbox"])
            if overlap >= iou_threshold:
                pairs.append((overlap, ref_index, cand_index))
    pairs.sort(reverse=True)
    used_ref: set[int] = set()
    used_candidate: set[int] = set()
    matches = []
    for overlap, ref_index, cand_index in pairs:
        if ref_index in used_ref or cand_index in used_candidate:
            continue
        used_ref.add(ref_index)
        used_candidate.add(cand_index)
        matches.append((ref_index, cand_index, overlap))
    return matches


def benchmark(payload: dict[str, Any], iou_threshold: float = 0.5) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BenchmarkInputError("Top-level JSON value must be an object.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise BenchmarkInputError(f"schema_version must be {SCHEMA_VERSION}.")
    reference_name = payload.get("reference_detector")
    candidate_name = payload.get("candidate_detector")
    if not isinstance(reference_name, str) or not reference_name.strip():
        raise BenchmarkInputError("reference_detector is required.")
    if not isinstance(candidate_name, str) or not candidate_name.strip():
        raise BenchmarkInputError("candidate_detector is required.")
    if payload.get("coordinate_space") != "source_frame_pixels":
        raise BenchmarkInputError("coordinate_space must be 'source_frame_pixels'.")
    frames = payload.get("frames")
    if not isinstance(frames, list) or not frames:
        raise BenchmarkInputError("frames must be a non-empty list.")

    seen_ids: set[str] = set()
    total_reference = total_candidate = matched = 0
    ious: list[float] = []
    landmark_errors: list[float] = []
    frame_rows = []

    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise BenchmarkInputError(f"frames[{frame_index}] must be an object.")
        frame_id = str(frame.get("frame_id", frame_index))
        if frame_id in seen_ids:
            raise BenchmarkInputError(f"Duplicate frame_id: {frame_id}")
        seen_ids.add(frame_id)
        width = _number(frame.get("width"), f"frames[{frame_index}].width")
        height = _number(frame.get("height"), f"frames[{frame_index}].height")
        if width <= 0 or height <= 0:
            raise BenchmarkInputError(f"frames[{frame_index}] dimensions must be positive.")
        ref_faces = _validate_faces(frame.get("reference_faces"), f"frames[{frame_index}].reference_faces")
        cand_faces = _validate_faces(frame.get("candidate_faces"), f"frames[{frame_index}].candidate_faces")
        pairs = _match_faces(ref_faces, cand_faces, iou_threshold)
        total_reference += len(ref_faces)
        total_candidate += len(cand_faces)
        matched += len(pairs)
        frame_ious = []
        frame_landmark_errors = []
        for ref_index, cand_index, overlap in pairs:
            frame_ious.append(overlap)
            ious.append(overlap)
            ref_landmarks = ref_faces[ref_index]["landmarks"]
            cand_landmarks = cand_faces[cand_index]["landmarks"]
            if ref_landmarks is not None and cand_landmarks is not None:
                error = _normalized_landmark_rmse(
                    ref_landmarks, cand_landmarks, ref_faces[ref_index]["bbox"]
                )
                frame_landmark_errors.append(error)
                landmark_errors.append(error)
        frame_rows.append({
            "frame_id": frame_id,
            "reference_faces": len(ref_faces),
            "candidate_faces": len(cand_faces),
            "matched_faces": len(pairs),
            "missed_reference_faces": len(ref_faces) - len(pairs),
            "extra_candidate_faces": len(cand_faces) - len(pairs),
            "mean_matched_iou": round(sum(frame_ious) / len(frame_ious), 6) if frame_ious else None,
            "mean_normalized_landmark_rmse": (
                round(sum(frame_landmark_errors) / len(frame_landmark_errors), 6)
                if frame_landmark_errors else None
            ),
        })

    precision = matched / total_candidate if total_candidate else (1.0 if total_reference == 0 else 0.0)
    recall = matched / total_reference if total_reference else 1.0
    return {
        "status": "benchmark_complete",
        "compatibility_verdict": "not_validated",
        "warning": (
            "Metrics compare supplied detections only. They do not certify GenD compatibility, "
            "crop equivalence, model accuracy, or legal/forensic suitability."
        ),
        "reference_detector": reference_name,
        "candidate_detector": candidate_name,
        "coordinate_space": "source_frame_pixels",
        "iou_match_threshold": iou_threshold,
        "frame_count": len(frames),
        "reference_face_count": total_reference,
        "candidate_face_count": total_candidate,
        "matched_face_count": matched,
        "missed_reference_face_count": total_reference - matched,
        "extra_candidate_face_count": total_candidate - matched,
        "detection_precision": round(precision, 6),
        "detection_recall": round(recall, 6),
        "mean_matched_iou": round(sum(ious) / len(ious), 6) if ious else None,
        "median_matched_iou": round(sorted(ious)[len(ious) // 2], 6) if ious else None,
        "mean_normalized_landmark_rmse": (
            round(sum(landmark_errors) / len(landmark_errors), 6) if landmark_errors else None
        ),
        "landmark_comparison_count": len(landmark_errors),
        "frames": frame_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare candidate face detections with a reference detector.")
    parser.add_argument("--input", required=True, type=Path, help="Benchmark input JSON.")
    parser.add_argument("--output", type=Path, help="Optional output JSON path.")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not 0.0 <= args.iou_threshold <= 1.0:
        parser.error("--iou-threshold must be between 0 and 1.")
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = benchmark(payload, args.iou_threshold)
    except (OSError, json.JSONDecodeError, BenchmarkInputError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
