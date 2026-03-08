from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI(title="Marifetli Llama3 Kesin Moderasyon")

class ModerationRequest(BaseModel):
    text: str

@app.post("/moderate")
async def moderate_text(request: ModerationRequest):
    # Çok daha sert, kriterleri net ve örnek içeren (Few-Shot) talimat seti
    system_prompt = (
        "Sen marifetli.com.tr topluluk muhafızısın. Görevin metni şu kriterlere göre denetlemektir:\n"
        "1. Küfür, hakaret, aşağılama (aptal, herif, gerizekalı vb.) = RED\n"
        "2. Beddua ve nefret söylemi (Allah belasını versin, kahrolsun vb.) = RED\n"
        "3. Siyaset, din tartışması veya cinsellik = RED\n"
        "4. Sadece el işi, hobi ve saygılı yorumlar = ONAY\n\n"
        "ÖRNEKLER:\n"
        "Kullanıcı: 'Harika bir örgü olmuş.' -> Cevap: ONAY\n"
        "Kullanıcı: 'Senin yapacağın işin belasını versin.' -> Cevap: RED\n"
        "Kullanıcı: 'Aptal mısın nesin?' -> Cevap: RED\n\n"
        "KESİN KURAL: Sadece tek bir kelime cevap ver: ONAY veya RED. Açıklama yapma!"
    )

    # Llama 3 Chat formatına tam uyumlu prompt yapısı
    full_prompt = (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
        f"<|start_header_id|>user<|end_header_id|>\n\nMetin: {request.text}<|eot_id|>"
        f"<|start_header_id|>assistant<|end_header_id|>\n\nCevap:"
    )

    payload = {
        "model": "llama3:latest",
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,  # Sıfır yaratıcılık, tam tutarlılık
            "num_predict": 5,    # Modelin gevezelik yapmasını engeller (Sadece ONAY/RED sığar)
            "stop": ["<|eot_id|>", "\n"] # Cevabı kısa keser
        }
    }

    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload)
        response.raise_for_status()
        
        res_json = response.json()
        # Modelin cevabını temizle (Boşlukları at, büyük harfe çevir)
        answer = res_json.get("response", "").strip().upper()
        
        # Loglama: Modelin ne dediğini terminalde gör (Hata ayıklamak için)
        print(f"Gelen Metin: {request.text} | Model Cevabı: {answer}")

        # Mantıksal Kontrol
        status = "RED" if "RED" in answer else "ONAY"
        return {"status": status}
        
    except Exception as e:
        print(f"HATA: {e}")
        return {"status": "RED", "detail": "Servis bağlantı hatası."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)