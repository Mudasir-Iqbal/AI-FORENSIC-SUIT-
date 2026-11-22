"""Evidence-preserving video intake and technical examination utilities.

This module deliberately does not classify a video as real or synthetic. It records
file integrity, container/stream metadata, and hashes of sampled working-copy frames.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat

MAX_VIDEO_BYTES = 250 * 1024 * 1024
MAX_VIDEO_SECONDS = 15 * 60
MAX_SAMPLED_FRAMES = 120
GEND_REQUIRED_FACE_FRAMES = 32
GEND_MODEL_ID = "yermandy/GenD_CLIP_L_14"
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}


class VideoExaminationError(ValueError):
    pass


def _run_json(command: list[str], timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoExaminationError("Video examination timed out during metadata inspection.") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or "Unknown media inspection error").strip()
        raise VideoExaminationError(f"Video could not be inspected: {detail[:300]}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VideoExaminationError("Media inspector returned invalid metadata.") from exc


def _fraction(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        result = float(Fraction(value))
        return round(result, 6) if result > 0 else None
    except (ValueError, ZeroDivisionError):
        return None


def examine_video_bytes(raw: bytes, filename: str) -> dict[str, Any]:
    """Inspect a bounded uploaded video and return verifiable technical evidence."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise VideoExaminationError(
            "Unsupported video format. Use MP4, WEBM, MOV, MKV, AVI, or M4V."
        )
    if not raw:
        raise VideoExaminationError("Uploaded video file is empty.")
    if len(raw) > MAX_VIDEO_BYTES:
        raise VideoExaminationError("Video exceeds the 250 MB upload limit.")

    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise RuntimeError("FFmpeg and FFprobe must be installed on the video worker.")

    original_sha256 = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix="deepguard-video-") as temp_dir:
        input_path = os.path.join(temp_dir, "original" + suffix)
        frames_dir = os.path.join(temp_dir, "sampled_frames")
        os.makedirs(frames_dir, exist_ok=True)
        with open(input_path, "wb") as output:
            output.write(raw)

        metadata = _run_json(
            [
                ffprobe, "-v", "error", "-show_format", "-show_streams",
                "-of", "json", input_path,
            ],
            timeout=30,
        )
        streams = metadata.get("streams") or []
        video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
        audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
        if not video_streams:
            raise VideoExaminationError("The uploaded file does not contain a video stream.")

        video = video_streams[0]
        fmt = metadata.get("format") or {}
        try:
            duration = float(fmt.get("duration") or video.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0:
            raise VideoExaminationError("Video duration could not be established.")
        if duration > MAX_VIDEO_SECONDS:
            raise VideoExaminationError("Video exceeds the 15-minute examination limit.")

        width = int(video.get("width") or 0)
        height = int(video.get("height") or 0)
        if width <= 0 or height <= 0 or width * height > 100_000_000:
            raise VideoExaminationError("Video dimensions are invalid or exceed 100 megapixels.")

        source_frame_rate = _fraction(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        reported_frames = int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else None
        estimated_source_frames = reported_frames or (
            int(round(duration * source_frame_rate)) if source_frame_rate else None
        )
        # GenD's published video preprocessing targets at least 32 face frames.
        # Sample 32 evenly spaced source frames when the source contains enough frames.
        # Never synthesize duplicate frames to satisfy this requirement.
        sample_fps = min(
            GEND_REQUIRED_FACE_FRAMES / duration,
            source_frame_rate or 1.0,
        )
        sample_interval = 1.0 / sample_fps
        frame_pattern = os.path.join(frames_dir, "frame_%04d.jpg")
        try:
            extraction = subprocess.run(
                [
                    ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", input_path, "-map", "0:v:0", "-an",
                    "-vf", f"fps={sample_fps:.10f},scale='min(640,iw)':-2",
                    "-frames:v", str(MAX_SAMPLED_FRAMES), "-q:v", "2", frame_pattern,
                ],
                capture_output=True, text=True, timeout=90, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise VideoExaminationError("Frame extraction timed out. Try a shorter or lower-resolution video.") from exc
        if extraction.returncode != 0:
            detail = (extraction.stderr or "Unknown frame extraction error").strip()
            raise VideoExaminationError(f"Video frames could not be extracted: {detail[:300]}")

        frame_files = sorted(Path(frames_dir).glob("frame_*.jpg"))
        if not frame_files:
            raise VideoExaminationError("No readable video frames could be extracted.")

        sampled_frames: list[dict[str, Any]] = []
        sharpness_values: list[float] = []
        brightness_values: list[float] = []
        contrast_values: list[float] = []
        for index, frame_path in enumerate(frame_files):
            frame_bytes = frame_path.read_bytes()
            with Image.open(frame_path) as frame:
                frame_width, frame_height = frame.size
                grayscale = frame.convert("L")
                edge_stats = ImageStat.Stat(grayscale.filter(ImageFilter.FIND_EDGES))
                image_stats = ImageStat.Stat(grayscale)
                sharpness = round(float(edge_stats.var[0]), 3)
                brightness = round(float(image_stats.mean[0]), 3)
                contrast = round(float(image_stats.stddev[0]), 3)
            sharpness_values.append(sharpness)
            brightness_values.append(brightness)
            contrast_values.append(contrast)
            sampled_frames.append(
                {
                    "sample_index": index,
                    "timestamp_seconds": round(index * sample_interval, 3),
                    "frame_sha256": hashlib.sha256(frame_bytes).hexdigest(),
                    "width": frame_width,
                    "height": frame_height,
                    "sharpness_proxy": sharpness,
                    "brightness_mean": brightness,
                    "contrast_stddev": contrast,
                    "working_copy_format": "JPEG",
                }
            )

        mean_sharpness = round(sum(sharpness_values) / len(sharpness_values), 3)
        mean_brightness = round(sum(brightness_values) / len(brightness_values), 3)
        mean_contrast = round(sum(contrast_values) / len(contrast_values), 3)
        quality_issues: list[dict[str, str]] = []
        if mean_sharpness < 12:
            quality_issues.append({
                "code": "LOW_SHARPNESS",
                "severity": "warning",
                "message": "Sampled frames appear heavily soft or blurred. Fine facial details may be unreliable.",
            })
        if mean_brightness < 35:
            quality_issues.append({
                "code": "LOW_BRIGHTNESS",
                "severity": "warning",
                "message": "Video is very dark; facial and texture details may be difficult to assess.",
            })
        elif mean_brightness > 220:
            quality_issues.append({
                "code": "HIGH_BRIGHTNESS",
                "severity": "warning",
                "message": "Video is very bright or overexposed; detail may be clipped.",
            })
        if mean_contrast < 18:
            quality_issues.append({
                "code": "LOW_CONTRAST",
                "severity": "warning",
                "message": "Video has low contrast; visual evidence may be limited.",
            })
        if len(frame_files) < min(8, max(1, int(duration))):
            quality_issues.append({
                "code": "INSUFFICIENT_SAMPLED_FRAMES",
                "severity": "warning",
                "message": "Fewer usable frames were extracted than expected for this clip duration.",
            })

        source_frame_gate_passed = estimated_source_frames is None or estimated_source_frames >= GEND_REQUIRED_FACE_FRAMES
        sampled_frame_gate_passed = len(sampled_frames) >= GEND_REQUIRED_FACE_FRAMES
        gend_blocking_reasons = []
        if not source_frame_gate_passed:
            gend_blocking_reasons.append(
                f"Source contains approximately {estimated_source_frames} frames; GenD video preprocessing requires at least {GEND_REQUIRED_FACE_FRAMES} candidate frames."
            )
        if not sampled_frame_gate_passed:
            gend_blocking_reasons.append(
                f"Only {len(sampled_frames)} distinct sampled frames were extracted; {GEND_REQUIRED_FACE_FRAMES} are required before face screening."
            )
        # The official RetinaFace/SCRFD detector weights used by the upstream
        # pipeline are not bundled here. Do not silently substitute another
        # detector or claim that model-ready aligned faces exist.
        gend_blocking_reasons.append(
            "GenD face detection and five-landmark alignment are not configured. The upstream SCRFD/InsightFace detector weights require a separate licensing and deployment review."
        )
        gend_blocking_reasons.append(
            "GenD runtime and checkpoint are not loaded in this backend; classification is therefore blocked."
        )
        gend_input_gate_status = "blocked" if gend_blocking_reasons else "passed"

        process_log = [
            {"step": "File validation", "status": "completed", "detail": "Extension, upload size and file presence validated."},
            {"step": "Media metadata inspection", "status": "completed", "detail": "FFprobe inspected container, streams, duration, codec and dimensions."},
            {"step": "Frame extraction", "status": "completed", "detail": f"Extracted {len(sampled_frames)} source frames at evenly spaced timestamps."},
            {"step": "Visual quality assessment", "status": "completed", "detail": f"Computed sharpness, brightness and contrast screening proxies across {len(sampled_frames)} frames."},
            {"step": "GenD input gate", "status": "blocked" if gend_input_gate_status == "blocked" else "completed", "detail": "; ".join(gend_blocking_reasons) if gend_blocking_reasons else "Input meets configured GenD preflight requirements."},
            {"step": "Face detection and five-point alignment", "status": "blocked", "detail": "Not run: a licensed and configured five-landmark face detector is required. No substitute detector is silently used."},
            {"step": "GenD image preprocessing", "status": "not_started", "detail": "Waiting for valid 256 × 256 aligned face crops and the official CLIP image processor."},
            {"step": "GenD model inference", "status": "blocked", "detail": "Not run because model-ready face crops and the isolated GenD runtime are not available."},
        ]

        def stream_summary(stream: dict[str, Any]) -> dict[str, Any]:
            return {
                "codec": stream.get("codec_name"),
                "codec_long_name": stream.get("codec_long_name"),
                "profile": stream.get("profile"),
                "sample_rate": int(stream["sample_rate"]) if str(stream.get("sample_rate") or "").isdigit() else None,
                "channels": stream.get("channels"),
                "pixel_format": stream.get("pix_fmt"),
                "width": stream.get("width"),
                "height": stream.get("height"),
                "frame_rate": _fraction(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
                "time_base": stream.get("time_base"),
                "bit_rate": int(stream["bit_rate"]) if str(stream.get("bit_rate", "")).isdigit() else None,
            }

        return {
            "examination_status": "evidence_prepared",
            "classification_status": "not_assessed",
            "classification_note": "Technical intake completed. GenD preflight is blocked until a licensed five-landmark face detector and isolated GenD runtime are configured.",
            "model_input_gate": {
                "model_id": GEND_MODEL_ID,
                "status": gend_input_gate_status,
                "minimum_candidate_frames": GEND_REQUIRED_FACE_FRAMES,
                "estimated_source_frames": estimated_source_frames,
                "sampled_source_frames": len(sampled_frames),
                "required_face_crop_size": [256, 256],
                "face_alignment": "five_landmark_similarity_alignment",
                "face_context_scale": 1.3,
                "face_detector_status": "not_configured_license_review_required",
                "model_runtime_status": "not_loaded",
                "blocking_reasons": gend_blocking_reasons,
                "automatic_enhancement_applied": False,
                "original_file_modified": False,
            },
            "processing_log": process_log,
            "quality_assessment": {
                "status": "review_required" if quality_issues else "no_obvious_quality_warning",
                "metrics_method": "PIL edge-response variance and grayscale intensity statistics; screening proxies only, not validated forensic quality scores.",
                "mean_sharpness_proxy": mean_sharpness,
                "mean_brightness": mean_brightness,
                "mean_contrast": mean_contrast,
                "issues": quality_issues,
                "automatic_enhancement_applied": False,
                "enhancement_note": "No deblurring, super-resolution, denoising or generative enhancement was applied. Such processing can invent or suppress forensic details and must be separately validated before model use.",
            },
            "evidence_integrity": {
                "original_filename": Path(filename).name,
                "file_size_bytes": len(raw),
                "sha256": original_sha256,
                "hash_algorithm": "SHA-256",
                "hash_scope": "Exact uploaded file bytes before media decoding.",
            },
            "video_metadata": {
                "container": fmt.get("format_name"),
                "duration_seconds": round(duration, 3),
                "width": width,
                "height": height,
                "display_aspect_ratio": video.get("display_aspect_ratio"),
                "frame_rate": _fraction(video.get("avg_frame_rate") or video.get("r_frame_rate")),
                "reported_frame_count": reported_frames,
                "video_codec": video.get("codec_name"),
                "pixel_format": video.get("pix_fmt"),
                "file_format_long_name": fmt.get("format_long_name"),
                "format_bit_rate": int(fmt["bit_rate"]) if str(fmt.get("bit_rate", "")).isdigit() else None,
                "video_stream_count": len(video_streams),
                "audio_stream_count": len(audio_streams),
                "audio_streams": [stream_summary(stream) for stream in audio_streams],
                "video_stream": stream_summary(video),
            },
            "frame_sampling": {
                "method": "FFmpeg constant-rate sampling across the clip duration",
                "target_max_frames": GEND_REQUIRED_FACE_FRAMES,
                "sample_interval_seconds": round(sample_interval, 6),
                "sampled_frame_count": len(sampled_frames),
                "frame_hashes": sampled_frames,
            },
            "analysis_tracks": {
                "face_manipulation": "not_assessed",
                "fully_ai_generated_video": "not_assessed",
                "audio_visual_synchronization": "not_assessed",
            },
            "evidence_handling": {
                "original_modified": False,
                "temporary_working_copy_used": True,
                "temporary_files_deleted_after_analysis": True,
                "persistent_evidence_storage": False,
                "chain_of_custody_status": "not_established_by_this_endpoint",
            },
            "limitations": [
                "This stage performs technical intake and preliminary visual-quality screening only; it does not classify authenticity.",
                "Sharpness, brightness and contrast values are screening proxies, not validated pass/fail thresholds for GenD or another detector.",
                "GenD classification is blocked until at least 32 candidate frames can be face-detected, five-landmark aligned to 256 × 256 crops, and passed through the official CLIP preprocessing pipeline.",
                "No deblurring or AI enhancement is applied; enhancement can create or remove details and may alter forensic evidence.",
                "Sampled frame hashes identify extracted working-copy frames, not the original encoded frame packets.",
                "The original upload and extracted frames are not persistently retained by this endpoint.",
                "A SHA-256 hash verifies byte identity, not the truthfulness or origin of the recording.",
            ],
        }
