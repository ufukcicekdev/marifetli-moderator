from fastapi import FastAPI
from pydantic import BaseModel
import requests
import json
import re # Düzenli ifadeler için ekledik

app = FastAPI(title="Marifetli Akıllı Moderasyon API")

class ModerationRequest(BaseModel):
    text: str

@app.post("/moderate")
async def moderate_text(request: ModerationRequest):
    # Promptu daha da daralttık
    system_prompt = (
        "Sen bir API servisisin. Görevin metni denetleyip SADECE JSON dönmektir. "
        "Format: {\"status\": \"RED\" veya \"ONAY\", \"bad_words\": []} "
        "Küfür, hakaret ve beddua varsa RED dön ve kelimeleri listele."
    )

    full_prompt = (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n\n{request.text}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )

    payload = {
        "model": "llama3:latest",
        "prompt": full_prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0}
    }

    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
        response.raise_for_status()
        
        raw_content = response.json().get("response", "{}").strip()
        
        # --- HATA ÇÖZÜCÜ KISIM ---
        # Eğer Llama 3 başına/sonuna yazı eklerse sadece { } arasını alıyoruz
        match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if match:
            clean_json_str = match.group(0)
            result = json.loads(clean_json_str)
        else:
            raise ValueError("JSON formatı bulunamadı")
        
        print(f"Başarılı Analiz: {result}")
        return result
        
    except Exception as e:
        print(f"HATA AYIKLAMA (Ham Metin): {raw_content if 'raw_content' in locals() else 'Yok'}")
        print(f"HATA DETAYI: {e}")
        return {
            "status": "RED", 
            "bad_words": [], 
            "detail": "Format hatası veya servis meşgul."
        }
    
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)