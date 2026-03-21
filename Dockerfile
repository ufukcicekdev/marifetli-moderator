# FastAPI moderasyon API — Ollama ayrı serviste (docker-compose) veya Railway’de OLLAMA_HTTP_URL ile
FROM python:3.12-slim-bookworm

WORKDIR /app

COPY requirements.txt main.py ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# Railway PORT; yerelde docker-compose PORT=8000
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
