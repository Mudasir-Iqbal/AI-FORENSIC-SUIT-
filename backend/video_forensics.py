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

from PIL import Image

MAX_VIDEO_BYTES = 250 * 1024 * 1024
MAX_VIDEO_SECONDS = 15 * 60
MAX_SAMPLED_FRAMES = 120
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

        sample_fps = min(1.0, MAX_SAMPLED_FRAMES / duration)
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
        for index, frame_path in enumerate(frame_files):
            frame_bytes = frame_path.read_bytes()
            with Image.open(frame_path) as frame:
                frame_width, frame_height = frame.size
            sampled_frames.append(
                {
                    "sample_index": index,
                    "timestamp_seconds": round(index * sample_interval, 3),
                    "frame_sha256": hashlib.sha256(frame_bytes).hexdigest(),
                    "width": frame_width,
                    "height": frame_height,
                    "working_copy_format": "JPEG",
                }
            )

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
            "classification_note": "No deepfake or AI-generated-video model has been run in this examination stage.",
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
                "reported_frame_count": int(video["nb_frames"]) if str(video.get("nb_frames", "")).isdigit() else None,
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
                "target_max_frames": MAX_SAMPLED_FRAMES,
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
                "This stage performs technical intake and frame sampling only; it does not classify authenticity.",
                "Sampled frame hashes identify extracted working-copy frames, not the original encoded frame packets.",
                "The original upload and extracted frames are not persistently retained by this endpoint.",
                "A SHA-256 hash verifies byte identity, not the truthfulness or origin of the recording.",
            ],
        }
