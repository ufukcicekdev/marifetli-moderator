FROM ollama/ollama:latest

# Gerekli araçları kur
RUN apt-get update && apt-get install -y python3 python3-pip curl

WORKDIR /app

# Bağımlılıkları kur (Hata veren bayrağı ekledik)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

COPY . .

# Başlatma scriptini oluştur
RUN echo '#!/bin/bash\n\
ollama serve &\n\
sleep 10\n\
ollama pull llama3\n\
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000' > start.sh && chmod +x start.sh

# Çalıştırma izni ver
RUN chmod +x /app/start.sh

# PORT'u dışarı aç
EXPOSE 8000

# OLLAMA'nın default entrypoint'ini ezerek kendi scriptimizi başlatıyoruz
ENTRYPOINT ["/bin/sh", "/app/start.sh"]