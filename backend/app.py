import asyncio
import ipaddress
import json
import io
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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from PIL import Image, ImageOps, UnidentifiedImageError
from transformers import AutoConfig, AutoFeatureExtractor, AutoImageProcessor, AutoModel, AutoModelForAudioClassification, AutoModelForImageClassification, AutoTokenizer, PreTrainedModel
from video_forensics import MAX_VIDEO_BYTES, VideoExaminationError, examine_video_bytes

MODEL_ID = os.getenv("TEXT_MODEL_ID", "desklib/ai-text-detector-v1.01")
AUDIO_MODEL_ID = os.getenv("AUDIO_MODEL_ID", "MelodyMachine/Deepfake-audio-detection-V2")
IMAGE_MODEL_ID = os.getenv("IMAGE_MODEL_ID", "aaronkantrowitz/ai-human-generated-image-detection")
IMAGE_MAX_BYTES = 15728640
IMAGE_MAX_PIXELS = 40000000
AUDIO_SAMPLE_RATE = 16000
AUDIO_MAX_SECONDS = int(os.getenv("AUDIO_MAX_SECONDS", "30"))
AUDIO_MAX_BYTES = 20971520
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
    app.state.audio_model = None
    app.state.audio_processor = None
    app.state.audio_model_status = "loading"
    app.state.audio_model_error = None
    app.state.image_model = None
    app.state.image_processor = None
    app.state.image_model_status = "loading"
    app.state.image_model_error = None

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

    try:
        logger.info("Loading audio detector: %s", AUDIO_MODEL_ID)
        audio_processor = AutoFeatureExtractor.from_pretrained(AUDIO_MODEL_ID)
        audio_model = AutoModelForAudioClassification.from_pretrained(AUDIO_MODEL_ID)
        audio_model.to(app.state.device)
        audio_model.eval()
        app.state.audio_processor = audio_processor
        app.state.audio_model = audio_model
        app.state.audio_model_status = "ready"
        logger.info("Audio detector loaded on %s", app.state.device)
    except Exception as exc:
        app.state.audio_model_status = "error"
        app.state.audio_model_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        logger.exception("Failed to load audio detector")

    try:
        logger.info("Loading image detector: %s", IMAGE_MODEL_ID)
        image_processor = AutoImageProcessor.from_pretrained(IMAGE_MODEL_ID)
        image_model = AutoModelForImageClassification.from_pretrained(IMAGE_MODEL_ID)
        image_model.to(app.state.device)
        image_model.eval()
        app.state.image_processor = image_processor
        app.state.image_model = image_model
        app.state.image_model_status = "ready"
        logger.info("Image detector loaded on %s", app.state.device)
    except Exception as exc:
        app.state.image_model_status = "error"
        app.state.image_model_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        logger.exception("Failed to load image detector")
    yield

    app.state.model = None
    app.state.tokenizer = None
    app.state.audio_model = None
    app.state.audio_processor = None
    app.state.image_model = None
    app.state.image_processor = None
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

class ImageDetectResponse(BaseModel):
    ai_probability: float
    is_ai_generated: bool
    label: str
    modality: str
    processing_time_ms: int
    model_id: str
    image_width: int
    image_height: int
    probabilities: dict[str, float]


@app.post("/detect-image", response_model=ImageDetectResponse)
async def detect_image(request: Request, file: UploadFile = File(...)) -> ImageDetectResponse:
    started = time.perf_counter()
    model = request.app.state.image_model
    processor = request.app.state.image_processor
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Image detection model is unavailable. Check /health.")

    filename = (file.filename or "").lower()
    allowed_extensions = (".jpg", ".jpeg", ".png", ".webp")
    if not filename.endswith(allowed_extensions):
        raise HTTPException(status_code=415, detail="Unsupported image format. Use JPG, JPEG, PNG, or WEBP.")

    raw = await file.read(IMAGE_MAX_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded image file is empty.")
    if len(raw) > IMAGE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image file exceeds the 15 MB upload limit.")

    try:
        with Image.open(io.BytesIO(raw)) as check_image:
            check_image.verify()
        with Image.open(io.BytesIO(raw)) as source_image:
            if source_image.width * source_image.height > IMAGE_MAX_PIXELS:
                raise ValueError("Image dimensions are too large. Maximum supported pixels: 40 million.")
            image = ImageOps.exif_transpose(source_image).convert("RGB")
            image_width, image_height = image.size

        inputs = processor(images=image, return_tensors="pt")
        inputs = {key: value.to(request.app.state.device) for key, value in inputs.items()}
        with torch.inference_mode():
            logits = model(**inputs).logits
            probabilities_tensor = torch.softmax(logits, dim=-1)[0]

        labels = {int(index): str(label).strip().lower() for index, label in model.config.id2label.items()}
        ai_index = next((index for index, label in labels.items() if any(term in label for term in ("ai-generated", "ai generated", "fake", "synthetic"))), None)
        real_index = next((index for index, label in labels.items() if any(term in label for term in ("human", "real", "authentic"))), None)
        if ai_index is None or real_index is None:
            raise ValueError(f"Image model labels do not identify both AI and real classes: {labels}")

        ai_probability = float(probabilities_tensor[ai_index].item())
        real_probability = float(probabilities_tensor[real_index].item())
        is_ai = ai_probability >= 0.5
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return ImageDetectResponse(
            ai_probability=round(ai_probability, 4),
            is_ai_generated=is_ai,
            label="AI-Generated Image" if is_ai else "Likely Real Image",
            modality="image",
            processing_time_ms=elapsed_ms,
            model_id=IMAGE_MODEL_ID,
            image_width=image_width,
            image_height=image_height,
            probabilities={"ai": round(ai_probability, 4), "real": round(real_probability, 4)},
        )
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Image could not be decoded. Upload a valid JPG, PNG, or WEBP image.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Image inference failed")
        raise HTTPException(status_code=500, detail="Image inference failed. Check server logs for details.") from exc
    finally:
        await file.close()


class AudioDetectResponse(BaseModel):
    ai_probability: float
    is_ai_generated: bool
    label: str
    modality: str
    processing_time_ms: int
    model_id: str
    audio_duration_seconds: float
    sample_rate: int
    probabilities: dict[str, float]


@app.post("/detect-audio", response_model=AudioDetectResponse)
async def detect_audio(request: Request, file: UploadFile = File(...)) -> AudioDetectResponse:
    started = time.perf_counter()
    model = request.app.state.audio_model
    processor = request.app.state.audio_processor
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Audio detection model is unavailable. Check /health.")

    filename = (file.filename or "").lower()
    allowed_extensions = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".webm")
    if not filename.endswith(allowed_extensions):
        raise HTTPException(status_code=415, detail="Unsupported audio format. Use WAV, MP3, OGG, M4A, FLAC, or WEBM.")

    raw = await file.read(AUDIO_MAX_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")
    if len(raw) > AUDIO_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio file exceeds the 20 MB upload limit.")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(status_code=503, detail="Audio decoder is not available on the server.")

    try:
        with tempfile.TemporaryDirectory(prefix="deepguard-audio-") as temp_dir:
            input_path = os.path.join(temp_dir, "input" + os.path.splitext(filename)[1])
            output_path = os.path.join(temp_dir, "audio.wav")
            with open(input_path, "wb") as input_file:
                input_file.write(raw)

            command = [
                ffmpeg, "-nostdin", "-v", "error", "-y",
                "-i", input_path, "-vn", "-ac", "1",
                "-ar", str(AUDIO_SAMPLE_RATE), "-t", str(AUDIO_MAX_SECONDS),
                "-f", "wav", "-acodec", "pcm_s16le", output_path,
            ]
            converted = subprocess.run(command, capture_output=True, timeout=25, check=False)
            if converted.returncode != 0 or not os.path.exists(output_path):
                raise ValueError("Audio could not be decoded. Please upload a valid audio file.")

            with wave.open(output_path, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                frames = wav_file.getnframes()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                if sample_rate != AUDIO_SAMPLE_RATE or channels != 1 or sample_width != 2:
                    raise ValueError("Audio preprocessing did not produce the required 16 kHz mono PCM format.")
                duration = frames / float(sample_rate)
                if duration < 1.0:
                    raise ValueError("Audio must be at least 1 second long.")
                audio_bytes = wav_file.readframes(frames)

        import numpy as np
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        inputs = processor(audio, sampling_rate=AUDIO_SAMPLE_RATE, return_tensors="pt", padding=True)
        inputs = {key: value.to(request.app.state.device) for key, value in inputs.items()}

        with torch.inference_mode():
            logits = model(**inputs).logits
            probabilities_tensor = torch.softmax(logits, dim=-1)[0]

        labels = {int(index): str(label).lower() for index, label in model.config.id2label.items()}
        fake_index = next((index for index, label in labels.items() if "fake" in label or "spoof" in label), None)
        real_index = next((index for index, label in labels.items() if "real" in label or "bonafide" in label or "bona fide" in label), None)
        if fake_index is None or real_index is None:
            raise ValueError("Audio model labels do not identify both fake and real classes.")

        fake_probability = float(probabilities_tensor[fake_index].item())
        real_probability = float(probabilities_tensor[real_index].item())
        is_fake = fake_probability >= 0.5
        elapsed_ms = round((time.perf_counter() - started) * 1000)

        return AudioDetectResponse(
            ai_probability=round(fake_probability, 4),
            is_ai_generated=is_fake,
            label="AI-Generated / Fake Audio" if is_fake else "Likely Real Audio",
            modality="audio",
            processing_time_ms=elapsed_ms,
            model_id=AUDIO_MODEL_ID,
            audio_duration_seconds=round(duration, 2),
            sample_rate=AUDIO_SAMPLE_RATE,
            probabilities={"fake": round(fake_probability, 4), "real": round(real_probability, 4)},
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="Audio decoding timed out. Try a shorter file.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Audio inference failed")
        raise HTTPException(status_code=500, detail="Audio inference failed. Check server logs for details.") from exc
    finally:
        await file.close()


@app.post("/video-forensics")
async def video_forensics_intake(file: UploadFile = File(...)) -> dict[str, Any]:
    """Prepare technical video evidence without making an authenticity verdict."""
    filename = file.filename or "uploaded_video"
    try:
        raw = await file.read(MAX_VIDEO_BYTES + 1)
        if len(raw) > MAX_VIDEO_BYTES:
            raise HTTPException(status_code=413, detail="Video exceeds the 250 MB upload limit.")
        try:
            return examine_video_bytes(raw, filename)
        except VideoExaminationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            logger.exception("Video forensic dependencies unavailable")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Video forensic intake failed")
            raise HTTPException(status_code=500, detail="Video forensic intake failed. Check server logs for details.") from exc
    finally:
        await file.close()


@app.post("/video-forensics/stream")
async def video_forensics_stream(file: UploadFile = File(...)):
    """Stream genuine processing-stage updates, then the completed evidence package."""
    filename = file.filename or "uploaded_video"
    try:
        raw = await file.read(MAX_VIDEO_BYTES + 1)
    finally:
        await file.close()

    if len(raw) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Video exceeds the 250 MB upload limit.")

    loop = asyncio.get_running_loop()
    progress_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def publish_progress(event: dict[str, str]) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, event)

    async def event_stream():
        yield "data: " + json.dumps({"type": "progress", "step": "Upload received", "status": "completed", "detail": "Upload received; starting technical examination."}) + "\\n\\n"
        task = asyncio.create_task(
            asyncio.to_thread(examine_video_bytes, raw, filename, publish_progress)
        )
        while not task.done():
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=0.25)
                yield "data: " + json.dumps(event) + "\\n\\n"
            except TimeoutError:
                continue

        while not progress_queue.empty():
            event = progress_queue.get_nowait()
            yield "data: " + json.dumps(event) + "\\n\\n"

        try:
            evidence = await task
            yield "data: " + json.dumps({"type": "complete", "result": evidence}) + "\\n\\n"
        except VideoExaminationError as exc:
            yield "data: " + json.dumps({"type": "error", "message": str(exc), "status_code": 400}) + "\\n\\n"
        except RuntimeError as exc:
            logger.exception("Video forensic streaming dependencies unavailable")
            yield "data: " + json.dumps({"type": "error", "message": str(exc), "status_code": 503}) + "\\n\\n"
        except Exception:
            logger.exception("Video forensic streaming failed")
            yield "data: " + json.dumps({"type": "error", "message": "Video forensic examination failed. Check server logs for details.", "status_code": 500}) + "\\n\\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "DeepGuard Backend API", "docs": "/docs"}


@app.get("/health")
def health_check(request: Request) -> dict[str, str | bool | None]:
    model_loaded = request.app.state.model is not None
    return {
        "status": "ok" if model_loaded else request.app.state.model_status,
        "model_loaded": model_loaded,
        "device": str(request.app.state.device),
        "model_id": MODEL_ID,
        "audio_model_loaded": request.app.state.audio_model is not None,
        "audio_model_status": request.app.state.audio_model_status,
        "audio_model_id": AUDIO_MODEL_ID,
        "audio_model_error": request.app.state.audio_model_error,
        "image_model_loaded": request.app.state.image_model is not None,
        "image_model_status": request.app.state.image_model_status,
        "image_model_id": IMAGE_MODEL_ID,
        "image_model_error": request.app.state.image_model_error,
        "video_forensics_available": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "video_forensics_endpoint": "/video-forensics",
        "video_classification_status": "not_implemented",
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
