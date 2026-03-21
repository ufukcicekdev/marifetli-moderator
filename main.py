from __future__ import annotations

import asyncio
import json
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any

import requests
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

GUVENLI_KELIMELER = {"makrome", "örgü", "dantel", "iğne oyası", "elişi", "hobi", "amigurumi", "kasnak"}


def _ollama_model_tag() -> str:
    m = os.environ.get("OLLAMA_MODEL", "llama3").strip()
    if not m:
        m = "llama3"
    return m if ":" in m else f"{m}:latest"


def _ollama_base_url() -> str:
    return os.environ.get("OLLAMA_HTTP_URL", "http://127.0.0.1:11434").rstrip("/")


def _ollama_startup_wait_seconds() -> float:
    raw = os.environ.get("OLLAMA_STARTUP_WAIT_SECONDS", "180").strip()
    try:
        return max(10.0, float(raw))
    except ValueError:
        return 180.0


def _ollama_generate_retries() -> int:
    raw = os.environ.get("OLLAMA_GENERATE_RETRIES", "5").strip()
    try:
        return max(1, min(int(raw), 10))
    except ValueError:
        return 5


async def _wait_for_ollama_api() -> None:
    base = _ollama_base_url()
    tags_url = f"{base}/api/tags"
    deadline = time.monotonic() + _ollama_startup_wait_seconds()
    while time.monotonic() < deadline:
        try:
            r = requests.get(tags_url, timeout=5)
            if r.status_code == 200:
                print(f"Ollama hazır → {base}", flush=True)
                return
        except requests.exceptions.RequestException:
            pass
        await asyncio.sleep(2)
    print(
        f"UYARI: {_ollama_startup_wait_seconds():.0f}s içinde Ollama yanıt vermedi ({tags_url}). "
        "İlk /moderate istekleri başarısız olabilir.",
        flush=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    base = _ollama_base_url()
    print(
        f"OLLAMA_HTTP_URL → {base} | model → {_ollama_model_tag()} "
        "(docker-compose: http://ollama:11434; Railway: private Ollama URL)",
        flush=True,
    )
    await _wait_for_ollama_api()
    yield


def _post_ollama_generate(payload: dict[str, Any]) -> requests.Response:
    url = f"{_ollama_base_url()}/api/generate"
    timeout = _ollama_http_timeout()
    retries = _ollama_generate_retries()
    last_err: BaseException | None = None
    for attempt in range(retries):
        try:
            return requests.post(url, json=payload, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(min(8.0, 1.5 * (attempt + 1)))
    assert last_err is not None
    raise last_err


app = FastAPI(title="Marifetli Akıllı Moderasyon API", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok", media_type="text/plain")


def _ollama_http_timeout() -> float:
    raw = os.environ.get("OLLAMA_HTTP_TIMEOUT_SECONDS", "180").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 180.0


def _moderation_num_predict() -> int:
    raw = os.environ.get("MODERATION_NUM_PREDICT", "64").strip()
    try:
        v = int(raw)
        return max(16, min(v, 512))
    except ValueError:
        return 64


class ModerationRequest(BaseModel):
    text: str


def _moderate_text_sync(text: str) -> dict[str, Any]:
    system_prompt = (
        "Sen marifetli.com.tr moderatörüsün. Görevin metni denetleyip JSON formatında cevap vermektir.\n"
        "Kurallar:\n"
        "1. Küfür, hakaret ve beddua varsa status: RED, yoksa status: ONAY.\n"
        "2. Sadece gerçek küfür ve hakaretleri bad_words listesine ekle.\n"
        "3. KESİN KURAL: 'makrome', 'örgü' gibi hobi terimlerini ASLA kötü kelime sayma.\n"
        'Cevap formatı: {"status": "RED", "bad_words": ["kelime1", "kelime2"]}'
    )

    full_prompt = (
        f"<|begin_of_text|>system\n\n{system_prompt}<|eot_id|>"
        f"user\n\nMetin: {text}<|eot_id|>"
        f"assistant\n\n"
    )

    payload = {
        "model": _ollama_model_tag(),
        "prompt": full_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.01,
            "num_predict": _moderation_num_predict(),
        },
    }

    raw_content = ""
    try:
        response = _post_ollama_generate(payload)
        response.raise_for_status()

        raw_content = response.json().get("response", "{}").strip()

        match = re.search(r"\{.*\}", raw_content, re.DOTALL)
        if not match:
            if any(word in raw_content.upper() for word in ["RED", "KÜFÜR", "HAKARET"]):
                return {"status": "RED", "bad_words": [], "detail": "Yapay zeka metni reddetti."}
            return {"status": "ONAY", "bad_words": []}

        result = json.loads(match.group(0))

        if "bad_words" in result:
            result["bad_words"] = [w for w in result["bad_words"] if w.lower() not in GUVENLI_KELIMELER]

        print(f"Başarılı Analiz: {result}")
        return result

    except Exception as e:
        print(f"HATA AYIKLAMA (Ham Metin): {raw_content}")
        err = str(e)
        hint = ""
        if "Connection refused" in err or "Failed to establish" in err:
            hint = (
                " Ollama adresi yanlış veya servis ayakta değil. Docker Compose: "
                "OLLAMA_HTTP_URL=http://ollama:11434 ve `ollama` servisinin çalıştığından emin ol. "
                "Railway: OLLAMA_HTTP_URL=http://<ollama>.railway.internal:11434 (private networking)."
            )
        return {"status": "RED", "bad_words": [], "detail": f"Hata: {err}{hint}"}


@app.post("/moderate")
async def moderate_text(request: ModerationRequest):
    return _moderate_text_sync(request.text)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
