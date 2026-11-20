import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

import torch
import torch.nn as nn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from transformers import AutoConfig, AutoModel, AutoTokenizer, PreTrainedModel

MODEL_ID = os.getenv("TEXT_MODEL_ID", "desklib/ai-text-detector-v1.01")
MAX_LEN = int(os.getenv("TEXT_MAX_LENGTH", "512"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "20000"))
THRESHOLD = float(os.getenv("TEXT_AI_THRESHOLD", "0.5"))

DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("deepguard.api")


class DesklibAIDetectionModel(PreTrainedModel):
    config_class = AutoConfig
    base_model_prefix = "model"

    def __init__(self, config: Any):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)
        self.post_init()

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        token_type_ids: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        # DeBERTa-v2 tokenizers may return token_type_ids. Forward them to
        # the backbone instead of rejecting them at this wrapper's boundary.
        model_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None:
            model_inputs["token_type_ids"] = token_type_ids

        outputs = self.model(**model_inputs)
        hidden_states = outputs.last_hidden_state

        if attention_mask is None:
            pooled = hidden_states.mean(dim=1)
        else:
            mask = attention_mask.unsqueeze(-1).to(hidden_states.dtype)
            pooled = (hidden_states * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)

        return {"logits": self.classifier(pooled)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model = None
    app.state.tokenizer = None
    app.state.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    app.state.model_status = "loading"

    try:
        logger.info("Loading text detector: %s", MODEL_ID)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = DesklibAIDetectionModel.from_pretrained(MODEL_ID)
        model.to(app.state.device)
        model.eval()

        app.state.tokenizer = tokenizer
        app.state.model = model
        app.state.model_status = "ready"
        logger.info("Text detector loaded on %s", app.state.device)
    except Exception:
        app.state.model_status = "error"
        logger.exception("Failed to load text detector")

    yield

    app.state.model = None
    app.state.tokenizer = None
    if app.state.device.type == "cuda":
        torch.cuda.empty_cache()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="DeepGuard Backend API",
    version="0.2.1",
    description="Model-backed multimodal content verification API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


class TextDetectRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_CHARS)

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text cannot be empty or whitespace only.")
        return value


class DetectResponse(BaseModel):
    ai_probability: float
    is_ai_generated: bool
    label: str
    modality: str
    processing_time_ms: int


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "DeepGuard Backend API", "docs": "/docs"}


@app.get("/health")
def health_check(request: Request) -> dict[str, str | bool]:
    model_loaded = request.app.state.model is not None
    return {
        "status": "ok" if model_loaded else request.app.state.model_status,
        "model_loaded": model_loaded,
        "device": str(request.app.state.device),
        "model_id": MODEL_ID,
    }


@app.post("/detect-text", response_model=DetectResponse)
def detect_text(req: TextDetectRequest, request: Request) -> DetectResponse:
    model = request.app.state.model
    tokenizer = request.app.state.tokenizer

    if model is None or tokenizer is None:
        raise HTTPException(
            status_code=503,
            detail="Text detection model is unavailable. Check the /health endpoint.",
        )

    start = time.perf_counter()
    try:
        encoded = tokenizer(
            req.text.strip(),
            padding=True,
            truncation=True,
            max_length=MAX_LEN,
            return_tensors="pt",
        )
        encoded = {
            key: value.to(request.app.state.device)
            for key, value in encoded.items()
        }

        with torch.inference_mode():
            outputs = model(**encoded)
            probability = torch.sigmoid(outputs["logits"].reshape(-1)[0]).item()

        if not 0.0 <= probability <= 1.0:
            raise ValueError("Model returned an invalid probability.")

    except Exception as exc:
        logger.exception("Text inference failed")
        raise HTTPException(
            status_code=500,
            detail="Text inference failed. Check server logs for details.",
        ) from exc

    elapsed_ms = round((time.perf_counter() - start) * 1000)
    is_ai = probability >= THRESHOLD

    return DetectResponse(
        ai_probability=round(probability, 4),
        is_ai_generated=is_ai,
        label="AI Generated" if is_ai else "Human Written",
        modality="text",
        processing_time_ms=elapsed_ms,
    )
