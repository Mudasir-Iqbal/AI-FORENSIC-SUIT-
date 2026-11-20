import ipaddress
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
import wave
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

import torch
import torch.nn as nn
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from transformers import AutoConfig, AutoModel, AutoModelForAudioClassification, AutoProcessor, AutoTokenizer, PreTrainedModel

MODEL_ID = os.getenv("TEXT_MODEL_ID", "desklib/ai-text-detector-v1.01")
MAX_LEN = int(os.getenv("TEXT_MAX_LENGTH", "512"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "20000"))
URL_TIMEOUT_SECONDS = float(os.getenv("URL_TIMEOUT_SECONDS", "5"))
URL_MAX_REDIRECTS = int(os.getenv("URL_MAX_REDIRECTS", "5"))
THRESHOLD = float(os.getenv("TEXT_AI_THRESHOLD", "0.5"))

DEFAULT_ORIGINS = (
    "https://ai-forensic-suite-cyan.vercel.app,"
    "http://localhost:5173,http://127.0.0.1:5173"
)
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
    version="0.3.0",
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


class URLDetectRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=4096)


class URLCheck(BaseModel):
    name: str
    status: str
    detail: str


class URLDetectResponse(BaseModel):
    risk_score: float
    is_suspicious: bool
    label: str
    modality: str
    processing_time_ms: int
    submitted_url: str
    final_url: str | None
    http_status: int | None
    redirect_count: int
    checks: list[URLCheck]
    reasons: list[str]


SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly",
    "is.gd", "buff.ly", "cutt.ly", "rb.gy",
}
SUSPICIOUS_TLDS = {
    "zip", "mov", "click", "country", "gq", "tk", "work",
    "support", "top", "rest", "cam",
}


def _validate_public_url(value: str) -> tuple[str, str, int | None]:
    cleaned = value.strip()
    if "://" not in cleaned:
        cleaned = "https://" + cleaned
    parsed = urlsplit(cleaned)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported.")
    if not parsed.hostname:
        raise ValueError("URL must include a valid hostname.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded username or password are not allowed.")
    try:
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("URL hostname or port is invalid.") from exc
    if not host or host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise ValueError("Local and private network destinations are not allowed.")

    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = {ipaddress.ip_address(item[4][0]) for item in resolved}
        except socket.gaierror as exc:
            raise ValueError("The domain could not be resolved through DNS.") from exc

    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Private, reserved, or non-public network destinations are blocked.")

    normalized = urlunsplit((parsed.scheme.lower(), host + (f":{port}" if port else ""), parsed.path or "/", parsed.query, ""))
    return normalized, host, port


@app.post("/detect-url", response_model=URLDetectResponse)
async def detect_url(req: URLDetectRequest) -> URLDetectResponse:
    started = time.perf_counter()
    checks: list[URLCheck] = []
    reasons: list[str] = []
    score = 0.0

    try:
        current_url, host, _ = _validate_public_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    parsed = urlsplit(current_url)
    checks.append(URLCheck(name="DNS resolution", status="pass", detail="Hostname resolves only to public IP addresses."))
    hostname = host
    is_ip = False
    try:
        ipaddress.ip_address(hostname)
        is_ip = True
    except ValueError:
        pass

    if parsed.scheme == "https":
        checks.append(URLCheck(name="HTTPS", status="pass", detail="URL uses HTTPS."))
    else:
        checks.append(URLCheck(name="HTTPS", status="warning", detail="URL uses unencrypted HTTP."))
        score += 15
        reasons.append("The URL uses HTTP rather than HTTPS.")

    if is_ip:
        score += 25
        reasons.append("The URL uses a raw IP address instead of a domain name.")
        checks.append(URLCheck(name="Host format", status="warning", detail="A raw IP address is used as the host."))
    else:
        labels = hostname.split(".")
        tld = labels[-1] if labels else ""
        if tld in SUSPICIOUS_TLDS:
            score += 15
            reasons.append(f"The domain uses the higher-risk .{tld} top-level domain.")
            checks.append(URLCheck(name="Top-level domain", status="warning", detail=f".{tld} is on the heuristic watchlist."))
        else:
            checks.append(URLCheck(name="Top-level domain", status="pass", detail="No watchlisted top-level domain pattern detected."))

        if "xn--" in hostname:
            score += 20
            reasons.append("The hostname contains punycode, which can be used in lookalike domains.")
            checks.append(URLCheck(name="Internationalized hostname", status="warning", detail="Punycode hostname detected."))

        if hostname in SHORTENER_DOMAINS:
            score += 15
            reasons.append("The URL uses a known URL-shortening domain, hiding its destination.")
            checks.append(URLCheck(name="URL shortener", status="warning", detail="Known URL shortener detected."))
        else:
            checks.append(URLCheck(name="URL shortener", status="pass", detail="No common URL shortener detected."))

        if len(labels) >= 5:
            score += 10
            reasons.append("The hostname contains an unusually large number of subdomains.")
            checks.append(URLCheck(name="Subdomain structure", status="warning", detail=f"{len(labels) - 2} subdomain labels detected."))

    if "@" in req.url:
        score += 20
        reasons.append("The URL contains an @ character, which can obscure the actual destination.")
        checks.append(URLCheck(name="URL obfuscation", status="warning", detail="An @ character appears in the submitted URL."))

    if len(parsed.query) > 180:
        score += 5
        reasons.append("The URL has an unusually long query string.")
        checks.append(URLCheck(name="Query string", status="warning", detail="Long query string detected."))

    redirect_count = 0
    http_status = None
    final_url: str | None = None
    current = current_url
    network_note = ""

    try:
        timeout = httpx.Timeout(URL_TIMEOUT_SECONDS, connect=URL_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, verify=True, headers={"User-Agent": "DeepGuard-URL-Inspector/1.0"}) as client:
            for hop in range(URL_MAX_REDIRECTS + 1):
                safe_url, _, _ = _validate_public_url(current)
                request = client.build_request("HEAD", safe_url)
                response = await client.send(request, stream=True)
                http_status = response.status_code
                location = response.headers.get("location")
                await response.aclose()
                final_url = safe_url

                if response.status_code in {301, 302, 303, 307, 308} and location:
                    if hop >= URL_MAX_REDIRECTS:
                        score += 10
                        reasons.append("The URL exceeded the redirect inspection limit.")
                        network_note = "Redirect limit reached; chain may be incomplete."
                        break
                    current = urljoin(safe_url, location)
                    redirect_count += 1
                    continue
                break

        if redirect_count:
            score += min(redirect_count * 5, 20)
            reasons.append(f"The URL redirects {redirect_count} time(s) before reaching its final destination.")
            checks.append(URLCheck(name="Redirect chain", status="warning" if redirect_count >= 2 else "info", detail=f"{redirect_count} redirect(s) followed."))
        else:
            checks.append(URLCheck(name="Redirect chain", status="pass", detail="No HTTP redirects detected."))

        checks.append(URLCheck(name="HTTP response", status="pass" if http_status and http_status < 400 else "warning", detail=f"Final HTTP status: {http_status or 'unavailable'}."))

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        network_note = str(exc)
        checks.append(URLCheck(name="Live connection", status="warning", detail=f"Could not complete live inspection: {network_note[:180]}"))

    score = round(min(max(score, 0.0), 100.0), 1)
    suspicious = score >= 40
    if not reasons:
        reasons.append("No high-risk heuristic indicators were detected during this scan.")
    if network_note:
        reasons.append("Live inspection was incomplete; this result should be treated as limited evidence.")

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    return URLDetectResponse(
        risk_score=score,
        is_suspicious=suspicious,
        label="Potentially Suspicious" if suspicious else "No Major Indicators Detected",
        modality="url",
        processing_time_ms=elapsed_ms,
        submitted_url=req.url,
        final_url=final_url,
        http_status=http_status,
        redirect_count=redirect_count,
        checks=checks,
        reasons=reasons,
    )


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
