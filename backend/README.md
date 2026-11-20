---
title: DeepGuard Text Detector
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# DeepGuard Text Detector

FastAPI inference service for the Desklib AI text detector.

## Endpoints

- `GET /` service information
- `GET /health` model loading and runtime status
- `POST /detect-text` model-backed text classification
- `GET /docs` interactive API documentation

The model is loaded from Hugging Face at application startup. Predictions are returned only when the model is available.
