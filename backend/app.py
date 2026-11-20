import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoConfig, AutoModel, PreTrainedModel

MODEL_ID = "desklib/ai-text-detector-v1.01"
MAX_LEN = 512
THRESHOLD = 0.5


class DesklibAIDetectionModel(PreTrainedModel):
    config_class = AutoConfig

    def __init__(self, config):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)
        self.init_weights()

    def forward(self, input_ids, attention_mask=None, labels=None):
        outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
        last_hidden_state = outputs[0]

        if attention_mask is None:
            pooled_output = last_hidden_state.mean(dim=1)
        else:
            input_mask_expanded = (
                attention_mask.unsqueeze(-1)
                .expand(last_hidden_state.size())
                .to(last_hidden_state.dtype)
            )
            sum_embeddings = torch.sum(last_hidden_state * input_mask_expanded, dim=1)
            sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
            pooled_output = sum_embeddings / sum_mask

        logits = self.classifier(pooled_output)
        loss = None
        if labels is not None:
            loss_fct = nn.BCEWithLogitsLoss()
            loss = loss_fct(logits.view(-1), labels.float())

        return {"logits": logits, "loss": loss}


app = FastAPI(title="DeepGuard Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = None
model = None


@app.on_event("startup")
def load_model():
    global tokenizer, model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = DesklibAIDetectionModel.from_pretrained(MODEL_ID)
    model.to(device)
    model.eval()


class TextDetectRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)


class DetectResponse(BaseModel):
    ai_probability: float
    is_ai_generated: bool
    label: str
    modality: str
    processing_time_ms: int


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "device": str(device),
    }


@app.post("/detect-text", response_model=DetectResponse)
def detect_text(req: TextDetectRequest):
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model is still loading")

    clean_text = req.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    start = time.perf_counter()

    encoded = tokenizer(
        clean_text,
        padding="max_length",
        truncation=True,
        max_length=MAX_LEN,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"].to(device)
    attention_mask = encoded["attention_mask"].to(device)

    with torch.no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        prob = torch.sigmoid(outputs["logits"]).item()

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    is_ai = prob >= THRESHOLD

    return DetectResponse(
        ai_probability=round(prob, 4),
        is_ai_generated=is_ai,
        label="AI Generated" if is_ai else "Human Written",
        modality="text",
        processing_time_ms=elapsed_ms,
    )
