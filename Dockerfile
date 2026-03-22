# FastAPI moderasyon API — AnythingLLM HTTP API (Gemini vb. AnythingLLM üzerinden)
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt main.py ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
