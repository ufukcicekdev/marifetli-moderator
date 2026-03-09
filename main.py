from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json
import re

app = FastAPI(title="Marifetli Akıllı Moderasyon API")

# Marifetli.com.tr için koruma altına alınmış kelimeler (Beyaz Liste)
GUVENLI_KELIMELER = {"makrome", "örgü", "dantel", "iğne oyası", "elişi", "hobi", "amigurumi", "kasnak"}

class ModerationRequest(BaseModel):
    text: str

@app.post("/moderate")
async def moderate_text(request: ModerationRequest):
    # Prompt'u netleştirdik ve örnekleri çoğalttık
    system_prompt = (
        "Sen marifetli.com.tr moderatörüsün. Görevin metni denetleyip JSON formatında cevap vermektir.\n"
        "Kurallar:\n"
        "1. Küfür, hakaret ve beddua varsa status: RED, yoksa status: ONAY.\n"
        "2. Sadece gerçek küfür ve hakaretleri bad_words listesine ekle.\n"
        "3. KESİN KURAL: 'makrome', 'örgü' gibi hobi terimlerini ASLA kötü kelime sayma.\n"
        "Cevap formatı: {\"status\": \"RED\", \"bad_words\": [\"kelime1\", \"kelime2\"]}"
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
        "format": "json",
        "options": {
            "temperature": 0.01, # Çok düşük yaratıcılık
            "num_predict": 100   # JSON'un kesilmemesi için yeterli uzunluk
        }
    }

    raw_content = ""
    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=45)
        response.raise_for_status()
        
        raw_content = response.json().get("response", "{}").strip()
        
        # JSON'u cımbızla çek
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if not match:
            # Eğer JSON bulamazsa manuel bir kontrol yapalım
            if any(word in raw_content.upper() for word in ["RED", "KÜFÜR", "HAKARET"]):
                return {"status": "RED", "bad_words": [], "detail": "Yapay zeka metni reddetti."}
            return {"status": "ONAY", "bad_words": []}

        result = json.loads(match.group(0))
        
        # --- BEYAZ LİSTE KONTROLÜ (Filtreleme) ---
        if "bad_words" in result:
            # Makrome gibi hobi kelimelerini listeden çıkar
            result["bad_words"] = [w for w in result["bad_words"] if w.lower() not in GUVENLI_KELIMELER]
            # Eğer sadece hobi kelimeleri kaldıysa status'u ONAY'a çek
            if not result["bad_words"] and result["status"] == "RED":
                # Eğer cümle içinde hala beddua/küfür varsa AI status'u RED bırakmış olabilir
                # Bu durumda status'u elle ONAY yapmıyoruz, AI'ya güveniyoruz ama listeyi temizliyoruz.
                pass

        print(f"Başarılı Analiz: {result}")
        return result
        
    except Exception as e:
        print(f"HATA AYIKLAMA (Ham Metin): {raw_content}")
        # Hata anında bile "güvenli" bir cevap dönelim
        return {"status": "RED", "bad_words": [], "detail": f"Hata: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)