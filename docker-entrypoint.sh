#!/bin/sh
set -eu

PORT="${PORT:-8000}"
MODEL="${OLLAMA_MODEL:-llama3}"

echo "Ollama sunucusu başlatılıyor (127.0.0.1:11434)…" >&2
ollama serve &
i=0
while [ "$i" -lt 180 ]; do
  if ollama list >/dev/null 2>&1; then
    echo "Ollama API hazır." >&2
    break
  fi
  i=$((i + 1))
  sleep 1
done

echo "Model: $MODEL — gerekirse indiriliyor…" >&2
ollama pull "$MODEL" || true

exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
