FROM python:3.11-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Build ke waqt model cache kar lein taake runtime par download ka wait kam ho
RUN python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('desklib/ai-text-detector-v1.01')"

COPY ./app.py /code/app.py

EXPOSE 7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
