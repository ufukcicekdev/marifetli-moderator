from __future__ import annotations

import json
import os
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Literal

import requests
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

GUVENLI_KELIMELER = {"makrome", "örgü", "dantel", "iğne oyası", "elişi", "hobi", "amigurumi", "kasnak"}


def _anythingllm_base_url() -> str:
    return os.environ.get("ANYTHINGLLM_BASE_URL", "").strip().rstrip("/")


def _anythingllm_api_key() -> str:
    return os.environ.get("ANYTHINGLLM_API_KEY", "").strip()


def _anythingllm_workspace_slug() -> str:
    return os.environ.get("ANYTHINGLLM_WORKSPACE_SLUG", "").strip()


def _anythingllm_chat_mode() -> str:
    m = os.environ.get("ANYTHINGLLM_CHAT_MODE", "chat").strip().lower()
    return m if m in ("automatic", "query", "chat") else "chat"


def _anythingllm_session_id() -> str | None:
    raw = os.environ.get("ANYTHINGLLM_SESSION_ID", "marifetli-moderate-api").strip()
    return raw or None


def _anythingllm_chat_session_id() -> str | None:
    raw = os.environ.get("ANYTHINGLLM_CHAT_SESSION_ID", "marifetli-chat-api").strip()
    return raw or None


def _http_timeout_seconds() -> float:
    raw = os.environ.get("ANYTHINGLLM_TIMEOUT_SECONDS", "180").strip()
    try:
        return max(10.0, float(raw))
    except ValueError:
        return 180.0


def _http_retries() -> int:
    raw = os.environ.get("ANYTHINGLLM_RETRIES", "5").strip()
    try:
        return max(1, min(int(raw), 10))
    except ValueError:
        return 5


def _chat_url() -> str | None:
    base = _anythingllm_base_url()
    slug = _anythingllm_workspace_slug()
    if not base or not slug:
        return None
    return f"{base}/api/v1/workspace/{slug}/chat"


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = _chat_url()
    print(
        f"AnythingLLM → base={_anythingllm_base_url() or '(ANYTHINGLLM_BASE_URL eksik)'} | "
        f"workspace={_anythingllm_workspace_slug() or '(ANYTHINGLLM_WORKSPACE_SLUG eksik)'} | "
        f"{'API anahtarı tanımlı' if _anythingllm_api_key() else 'ANYTHINGLLM_API_KEY eksik'}",
        flush=True,
    )
    if url:
        print(f"Chat endpoint: {url}", flush=True)
    yield


app = FastAPI(title="Marifetli Akıllı Moderasyon API", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok", media_type="text/plain")


class ModerationRequest(BaseModel):
    text: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Kullanıcı mesajı (AnythingLLM’e iletilir).")
    mode: Literal["automatic", "query", "chat"] | None = Field(
        default=None,
        description="Boşsa ANYTHINGLLM_CHAT_MODE veya 'chat' kullanılır.",
    )
    session_id: str | None = Field(
        default=None,
        description="Sohbet oturumu; boşsa ANYTHINGLLM_CHAT_SESSION_ID (varsayılan marifetli-chat-api).",
    )
    reset: bool = Field(default=False, description="AnythingLLM reset bayrağı.")


def _resolve_chat_mode(mode: str | None) -> str:
    m = (mode or _anythingllm_chat_mode()).strip().lower()
    return m if m in ("automatic", "query", "chat") else "chat"


def _post_anythingllm_chat(
    message: str,
    *,
    mode: str | None = None,
    session_id: str | None = None,
    reset: bool = False,
) -> requests.Response:
    url = _chat_url()
    if not url:
        raise ValueError(
            "ANYTHINGLLM_BASE_URL ve ANYTHINGLLM_WORKSPACE_SLUG ortam değişkenleri zorunlu."
        )
    key = _anythingllm_api_key()
    if not key:
        raise ValueError("ANYTHINGLLM_API_KEY ortam değişkeni zorunlu.")

    payload: dict[str, Any] = {
        "message": message,
        "mode": _resolve_chat_mode(mode),
        "reset": reset,
    }
    sid = session_id
    if sid:
        payload["sessionId"] = sid

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    timeout = _http_timeout_seconds()
    retries = _http_retries()
    last_err: BaseException | None = None
    for attempt in range(retries):
        try:
            return requests.post(url, json=payload, headers=headers, timeout=timeout)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(min(8.0, 1.5 * (attempt + 1)))
    assert last_err is not None
    raise last_err


def _moderate_text_sync(text: str) -> dict[str, Any]:
    system_prompt = (
        "Sen marifetli.com.tr moderatörüsün. Görevin metni denetleyip YALNIZCA geçerli bir JSON nesnesi "
        "olarak cevap vermektir; başka metin veya açıklama yazma.\n"
        "Kurallar:\n"
        "1. Küfür, hakaret ve beddua varsa status: RED, yoksa status: ONAY.\n"
        "2. Sadece gerçek küfür ve hakaretleri bad_words listesine ekle.\n"
        "3. KESİN KURAL: 'makrome', 'örgü' gibi hobi terimlerini ASLA kötü kelime sayma.\n"
        'Cevap formatı: {"status": "RED", "bad_words": ["kelime1", "kelime2"]} veya '
        '{"status": "ONAY", "bad_words": []}'
    )

    user_block = f"Metin: {text}\n\nYanıtın yalnızca JSON olsun."
    message = f"{system_prompt}\n\n{user_block}"

    raw_content = ""
    try:
        mod_sid = _anythingllm_session_id()
        response = _post_anythingllm_chat(
            message,
            mode=_anythingllm_chat_mode(),
            session_id=mod_sid,
            reset=False,
        )
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {}

        if not response.ok:
            api_err = body.get("error") if isinstance(body, dict) else None
            err = api_err or f"HTTP {response.status_code}"
            hint = ""
            if response.status_code in (401, 403):
                hint = " ANYTHINGLLM_API_KEY geçersiz veya eksik; AnythingLLM’de yeni API anahtarı oluştur."
            return {"status": "RED", "bad_words": [], "detail": f"Hata: {err}{hint}"}

        if body.get("type") == "abort" or body.get("error"):
            err = body.get("error") or "AnythingLLM isteği iptal oldu."
            return {"status": "RED", "bad_words": [], "detail": str(err)}

        raw_content = (body.get("textResponse") or "").strip()

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
            hint = " AnythingLLM sunucusuna ulaşılamıyor; ANYTHINGLLM_BASE_URL ve ağ erişimini kontrol et."
        elif "ANYTHINGLLM_" in err and "eksik" in err:
            hint = ""
        return {"status": "RED", "bad_words": [], "detail": f"Hata: {err}{hint}"}


@app.post("/moderate")
async def moderate_text(request: ModerationRequest):
    return _moderate_text_sync(request.text)


def _chat_sync(req: ChatRequest) -> dict[str, Any]:
    if req.session_id is None:
        sid = _anythingllm_chat_session_id()
    else:
        sid = req.session_id.strip() or None
    try:
        response = _post_anythingllm_chat(
            req.message.strip(),
            mode=req.mode,
            session_id=sid,
            reset=req.reset,
        )
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = {}

        if not response.ok:
            api_err = body.get("error") if isinstance(body, dict) else None
            err = api_err or f"HTTP {response.status_code}"
            hint = ""
            if response.status_code in (401, 403):
                hint = " ANYTHINGLLM_API_KEY geçersiz veya eksik."
            return {"ok": False, "detail": f"{err}{hint}"}

        if not isinstance(body, dict):
            return {"ok": False, "detail": "Beklenmeyen AnythingLLM yanıtı."}

        if body.get("type") == "abort" or body.get("error"):
            return {
                "ok": False,
                "detail": str(body.get("error") or "AnythingLLM isteği iptal oldu."),
            }

        return {
            "ok": True,
            "id": body.get("id"),
            "type": body.get("type"),
            "text": body.get("textResponse"),
            "sources": body.get("sources") if isinstance(body.get("sources"), list) else [],
            "close": body.get("close"),
        }

    except Exception as e:
        err = str(e)
        hint = ""
        if "Connection refused" in err or "Failed to establish" in err:
            hint = " AnythingLLM sunucusuna ulaşılamıyor."
        return {"ok": False, "detail": f"{err}{hint}"}


@app.post("/chat")
async def chat(request: ChatRequest):
    return _chat_sync(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
