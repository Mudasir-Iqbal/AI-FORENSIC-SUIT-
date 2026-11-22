"""Isolated GenD inference worker.

This app intentionally has its own PyTorch/Transformers stack. It does not change
the production FastAPI environment. Inputs are candidate face crops; callers must
label scores experimental until their detector/crop pipeline is validated.
"""
from __future__ import annotations

import hashlib
import io
import os
import time
from typing import Any

import modal

APP_NAME = "deepguard-gend"
MODEL_ID = "yermandy/GenD_CLIP_L_14"
MODEL_REVISION = os.getenv("GEND_MODEL_REVISION", "main")
MODEL_SHA256 = "d76f0bdfd74a29fe1b1c1b84a80ac92486993e426878e8c7a3944281fbb96833"
MAX_CROPS = 120
MAX_CROP_BYTES = 2 * 1024 * 1024
MAX_BATCH_BYTES = 32 * 1024 * 1024

app = modal.App(APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        "torch==2.8.0",
        "torchvision==0.23.0",
        "transformers==4.56.2",
        "safetensors==0.6.2",
        "Pillow==11.3.0",
        "huggingface_hub==0.34.4",
    )
    .run_commands(
        "git clone https://github.com/yermandy/GenD.git /opt/GenD",
        "cd /opt/GenD && git checkout 387a42266dd385fbe8f7626c5d3aa03eea3bfaab",
    )
    .env({"PYTHONPATH": "/opt/GenD"})
)

_model = None
_device = None


def _load_model():
    global _model, _device
    if _model is not None:
        return _model, _device

    import sys
    sys.path.insert(0, "/opt/GenD")
    import torch
    from huggingface_hub import hf_hub_download
    from src.hf.modeling_gend import GenD

    checkpoint_path = hf_hub_download(
        repo_id=MODEL_ID, filename="model.safetensors", revision=MODEL_REVISION
    )
    digest = hashlib.sha256()
    with open(checkpoint_path, "rb") as checkpoint:
        for chunk in iter(lambda: checkpoint.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise RuntimeError("GenD checkpoint SHA-256 does not match the pinned artifact.")

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GenD.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model.to(_device)
    model.eval()
    _model = model
    return _model, _device


@app.function(
    image=image,
    cpu=8,
    memory=16384,
    timeout=900,
    scaledown_window=300,
)
def infer_candidate_crops(crops: list[bytes]) -> dict[str, Any]:
    """Run GenD on pre-aligned candidate crops and return raw class probabilities.

    This function does not certify the upstream detector/crop equivalence. The
    current YuNet path is experimental and its scores must not be treated as a
    validated video-level authenticity verdict.
    """
    if not crops or len(crops) > MAX_CROPS:
        raise ValueError(f"Provide between 1 and {MAX_CROPS} face crops.")
    total_bytes = sum(len(item) for item in crops)
    if any(not item or len(item) > MAX_CROP_BYTES for item in crops):
        raise ValueError("Each crop must be non-empty and no larger than 2 MiB.")
    if total_bytes > MAX_BATCH_BYTES:
        raise ValueError("Crop batch exceeds the 32 MiB limit.")

    from PIL import Image
    import torch

    started = time.perf_counter()
    model, device = _load_model()
    tensors = []
    crop_hashes = []
    for raw in crops:
        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGB")
            if image.size != (256, 256):
                raise ValueError("GenD candidate crops must be exactly 256 x 256 pixels.")
            tensors.append(model.feature_extractor.preprocess(image))
        crop_hashes.append(hashlib.sha256(raw).hexdigest())

    batch = torch.stack(tensors).to(device)
    with torch.inference_mode():
        logits = model(batch)
        if logits.ndim != 2 or logits.shape != (len(crops), 2):
            raise RuntimeError(f"Unexpected GenD output shape: {tuple(logits.shape)}")
        probabilities = torch.softmax(logits.float(), dim=-1)
        if not torch.isfinite(probabilities).all():
            raise RuntimeError("GenD returned non-finite probabilities.")

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    rows = []
    for index, (logit, probability) in enumerate(zip(logits.cpu(), probabilities.cpu())):
        rows.append({
            "crop_index": index,
            "crop_sha256": crop_hashes[index],
            "logits": [round(float(value), 7) for value in logit.tolist()],
            "class_probabilities": {
                "class_0": round(float(probability[0]), 7),
                "class_1": round(float(probability[1]), 7),
            },
        })

    return {
        "status": "experimental_inference_complete",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_checkpoint_sha256_expected": MODEL_SHA256,
        "class_mapping": "unverified; probabilities are exposed by raw class index only",
        "preprocessing_status": "caller_supplied_256x256_candidates_not_official_detector_validated",
        "verdict_status": "not_assessed",
        "device": str(device),
        "crop_count": len(rows),
        "processing_time_ms": elapsed_ms,
        "results": rows,
        "warning": (
            "Per-crop model scores only. The caller's face detector and crop pipeline "
            "must be validated against official GenD preprocessing before scores can "
            "support a video-level authenticity verdict."
        ),
    }


@app.function(image=image, cpu=1, memory=1024, timeout=30)
def health() -> dict[str, str]:
    return {
        "service": APP_NAME,
        "status": "ready_to_load",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
    }
