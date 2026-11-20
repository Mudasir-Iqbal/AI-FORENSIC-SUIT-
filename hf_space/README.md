---
title: DeepGuard Text Detector
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: gradio
python_version: "3.12"
app_file: app.py
pinned: false
---

# DeepGuard Text Detector

Gradio + ZeroGPU deployment of `desklib/ai-text-detector-v1.01`.

The public API endpoint is `/detect_text`. It returns a JSON object containing
`ai_probability`, `is_ai_generated`, `label`, `modality`, and
`processing_time_ms`.

Predictions are probabilistic and are not conclusive proof of authorship.
