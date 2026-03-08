from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json

app = FastAPI(title="Marifetli Akıllı Moderasyon API")

class ModerationRequest(BaseModel):
    text: str

@app.post("/moderate")
async def moderate_text(request: ModerationRequest):
    # JSON formatında cevap vermesi için zorluyoruz
    system_prompt = (
        "Sen marifetli.com.tr topluluk denetleyicisisin. "
        "Görevin metni küfür, hakaret, beddua ve siyaset açısından incelemektir. "
        "Cevabını mutlaka şu JSON formatında ver:\n"
        "{\n"
        "  \"status\": \"RED\" veya \"ONAY\",\n"
        "  \"bad_words\": [tespit edilen hakaret veya küfürlerin listesi]\n"
        "}\n"
        "Eğer metin temizse 'status': 'ONAY' ve 'bad_words': [] olmalı.\n"
        "Asla açıklama yapma, SADECE JSON döndür."
    )

    full_prompt = (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n\nMetin: {request.text}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )

    payload = {
        "model": "llama3:latest",
        "prompt": full_prompt,
        "stream": False,
        "format": "json", # Ollama'nın JSON modunu aktif ediyoruz
        "options": {
            "temperature": 0.0,
            "stop": ["<|eot_id|>", "\n"]
        }
    }

    try:
        # Ollama'ya istek atıyoruz
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()
        
        res_json = response.json()
        ai_response_str = res_json.get("response", "{}")
        
        # Llama'dan gelen string'i Python sözlüğüne çeviriyoruz
        result = json.loads(ai_response_str)
        
        # Loglama (Hangi kelimeleri bulduğunu terminalde gör)
        print(f"İşlenen Metin: {request.text} | Sonuç: {result}")

        return result
        
    except Exception as e:
        print(f"HATA: {e}")
        return {
            "status": "RED", 
            "bad_words": [], 
            "detail": "Servis hatası nedeniyle güvenlik gereği RED dönüldü."
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)