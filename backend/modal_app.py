import sys

import modal

app = modal.App("deepguard-api")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
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
