import os
import time

import gradio as gr
import spaces
import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoTokenizer, PreTrainedModel

MODEL_ID = os.getenv("TEXT_MODEL_ID", "desklib/ai-text-detector-v1.01")
MAX_LENGTH = int(os.getenv("TEXT_MAX_LENGTH", "512"))
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "20000"))
AI_THRESHOLD = float(os.getenv("TEXT_AI_THRESHOLD", "0.5"))

class DesklibAIDetectionModel(PreTrainedModel):
    config_class = AutoConfig
    base_model_prefix = "model"

    def __init__(self, config):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)
        self.post_init()

    def forward(self, input_ids, attention_mask=None, token_type_ids=None):
        model_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if token_type_ids is not None:
            model_inputs["token_type_ids"] = token_type_ids
        outputs = self.model(**model_inputs)
        hidden = outputs.last_hidden_state

        if attention_mask is None:
            pooled = hidden.mean(dim=1)
        else:
            mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)

        return {"logits": self.classifier(pooled)}

# ZeroGPU requires models to be initialized and placed on CUDA at module scope.
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = DesklibAIDetectionModel.from_pretrained(MODEL_ID)
model.to("cuda")
model.eval()

@spaces.GPU(duration=45)
def detect_text(text: str) -> dict:
    """Classify submitted text with the Desklib AI-text detector.

    Returns the model's AI probability, threshold-based label, modality,
    and measured inference time. This is a probabilistic detector, not proof
    of authorship.
    """
    if not isinstance(text, str) or not text.strip():
        raise gr.Error("Please enter some text.")
    if len(text) > MAX_TEXT_CHARS:
        raise gr.Error(f"Text exceeds the {MAX_TEXT_CHARS:,}-character limit.")

    started = time.perf_counter()
    encoded = tokenizer(
        text.strip(),
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    encoded = {key: value.to("cuda") for key, value in encoded.items()}

    with torch.inference_mode():
        logits = model(**encoded)["logits"]
        probability = float(torch.sigmoid(logits.reshape(-1)[0]).item())

    if not 0.0 <= probability <= 1.0:
        raise gr.Error("The model returned an invalid probability.")

    is_ai = probability >= AI_THRESHOLD
    return {
        "ai_probability": round(probability, 4),
        "is_ai_generated": is_ai,
        "label": "AI Generated" if is_ai else "Human Written",
        "modality": "text",
        "processing_time_ms": round((time.perf_counter() - started) * 1000),
        "threshold": AI_THRESHOLD,
        "model_id": MODEL_ID,
        "note": "Probabilistic model output. It is not conclusive proof of authorship.",
    }

with gr.Blocks(title="DeepGuard Text Detector") as demo:
    gr.Markdown(
        "# DeepGuard Text Detector\n"
        "Model-backed AI-text analysis using the Desklib detector. "
        "Results are probabilistic and should not be treated as definitive proof."
    )
    text_input = gr.Textbox(
        label="Text to analyze",
        placeholder="Paste the text you want to analyze...",
        lines=10,
        max_lines=20,
    )
    analyze_button = gr.Button("Analyze text", variant="primary")
    result_output = gr.JSON(label="Detection result")
    analyze_button.click(
        fn=detect_text,
        inputs=text_input,
        outputs=result_output,
        api_name="detect_text",
    )

demo.queue(default_concurrency_limit=1).launch()
