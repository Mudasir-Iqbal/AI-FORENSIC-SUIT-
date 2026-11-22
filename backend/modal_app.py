import sys

import modal

app = modal.App("deepguard-api")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "curl")
    .run_commands(
        "mkdir -p /opt/models && "
        "curl -fsSL 'https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/face_detection_yunet/face_detection_yunet_2023mar.onnx' "
        "-o /opt/models/face_detection_yunet_2023mar.onnx && "
        "echo '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4  /opt/models/face_detection_yunet_2023mar.onnx' | sha256sum -c -"
    )
    .pip_install_from_requirements("backend/requirements.txt")
    .add_local_dir("backend", remote_path="/root/backend")
)


@app.function(
    image=image,
    cpu=4,
    memory=8192,
    timeout=900,
    scaledown_window=300,
)
@modal.asgi_app()
def create_api():
    sys.path.insert(0, "/root/backend")
    from app import app as fastapi_app

    return fastapi_app
