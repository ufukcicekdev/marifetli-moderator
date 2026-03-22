# marifetli-moderator

**FastAPI** ile metin moderasyonu: [AnythingLLM](https://docs.anythingllm.com/features/api) workspace chat API üzerinden (ör. Gemini) JSON cevap üretir.

## Ortam değişkenleri

| Değişken | Zorunlu | Açıklama |
|----------|---------|----------|
| `ANYTHINGLLM_BASE_URL` | Evet | Örn. `https://senin-anythingllm.up.railway.app` (sonunda `/` yok) |
| `ANYTHINGLLM_API_KEY` | Evet | AnythingLLM → Developer API anahtarı (`Bearer` ile gider) |
| `ANYTHINGLLM_WORKSPACE_SLUG` | Evet | Workspace slug (URL’deki çalışma alanı) |
| `ANYTHINGLLM_CHAT_MODE` | Hayır | `chat` (varsayılan), `automatic` veya `query` |
| `ANYTHINGLLM_SESSION_ID` | Hayır | `/moderate` için oturum; varsayılan `marifetli-moderate-api` |
| `ANYTHINGLLM_CHAT_SESSION_ID` | Hayır | `/chat` için varsayılan oturum; varsayılan `marifetli-chat-api` (boşsa `sessionId` gönderilmez) |
| `ANYTHINGLLM_TIMEOUT_SECONDS` | Hayır | Varsayılan `180` |
| `PORT` | Hayır | Railway / container portu; varsayılan `8000` |

Uç nokta: `{ANYTHINGLLM_BASE_URL}/api/v1/workspace/{slug}/chat`. Örnek şema: kendi kurulumunuzda `/api/docs`.

## Yerelde Docker

1. Proje kökünde `.env` oluşturup en azından `ANYTHINGLLM_API_KEY` yazın (repoya eklemeyin).

2. `docker compose up --build`

3. Test:
   ```bash
   curl -s http://127.0.0.1:8000/healthz
   curl -s -X POST http://127.0.0.1:8000/moderate \
     -H "Content-Type: application/json" \
     -d '{"text":"merhaba makrome"}'
   curl -s -X POST http://127.0.0.1:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"Merhaba, makrome ipuçları verir misin?"}'
   ```

4. Swagger: http://127.0.0.1:8000/docs

## Railway

Moderasyon servisinin **Variables** içine `ANYTHINGLLM_BASE_URL`, `ANYTHINGLLM_API_KEY`, `ANYTHINGLLM_WORKSPACE_SLUG` ekleyin; ardından yeniden deploy edin.

**Health check:** `/healthz` · **Public port:** `PORT` (Railway otomatik).

## Sadece Python (Docker’sız)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANYTHINGLLM_BASE_URL=... ANYTHINGLLM_API_KEY=... ANYTHINGLLM_WORKSPACE_SLUG=...
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API

| Yöntem | Yol | Açıklama |
|--------|-----|----------|
| GET | `/healthz` | `ok` |
| POST | `/moderate` | Gövde: `{"text":"..."}` — moderasyon JSON’u |
| POST | `/chat` | Gövde: `{"message":"...", "mode"?: "chat"|"query"|"automatic", "session_id"?: "...", "reset"?: false}` — genel sohbet |
