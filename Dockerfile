# Tek konteyner: Ollama (arkaplan) + FastAPI. Railway veya docker-compose ile aynı imaj.
FROM ollama/ollama:latest

USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-venv \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt main.py ./
RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
