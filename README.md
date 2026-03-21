# marifetli-moderator

**FastAPI** ile metin moderasyonu: Ollama `/api/generate` üzerinden JSON cevap üretir.

## Yerelde Docker

1. `.env` (isteğe bağlı — `OLLAMA_MODEL` vb.):
   ```bash
   cp .env.example .env
   ```

2. Ayağa kaldır (**Ollama** + **app**):
   ```bash
   docker compose up -d --build
   ```

3. Ollama’ya model çek (ilk sefer):
   ```bash
   docker compose exec ollama ollama pull llama3
   ```

4. Test:
   ```bash
   curl -s http://127.0.0.1:8000/healthz
   curl -s -X POST http://127.0.0.1:8000/moderate \
     -H "Content-Type: application/json" \
     -d '{"text":"merhaba makrome"}'
   ```

5. Swagger: http://127.0.0.1:8000/docs  

`app` servisi `OLLAMA_HTTP_URL=http://ollama:11434` ile compose içindeki Ollama’ya bağlanır.

## Railway

Bu imaj **sadece FastAPI** çalıştırır; konteyner içinde **Ollama yok**. `127.0.0.1:11434` varsayılanı Railway’de **Connection refused** verir.

1. Aynı projede **`ollama/ollama`** ile ikinci bir servis aç (volume: `/root/.ollama`, model: shell’den `ollama pull …`).
2. **Her iki serviste** de **Private Networking** açık olsun.
3. Moderasyon servisinin **Variables**:
   - `OLLAMA_HTTP_URL=http://OLLAMA-SERVIS-ADIN.railway.internal:11434`  
     (`OLLAMA-SERVIS-ADIN` = Railway’de Ollama servisine verdiğin isim, örn. `ollama`).
4. Moderasyon servisini **yeniden deploy** et.

**Health check:** `/healthz` · **Public port:** `PORT` (Railway otomatik).

## Sadece Python (Docker’sız)

Ollama’nın `http://127.0.0.1:11434` adresinde çalışıyor olması gerekir.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API

| Yöntem | Yol | Açıklama |
|--------|-----|----------|
| GET | `/healthz` | `ok` |
| POST | `/moderate` | Gövde: `{"text":"..."}` |
