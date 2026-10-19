# 1) Temel: İçinde Python 3.12 kurulu, küçültülmüş bir Linux
FROM python:3.12-slim

# 2) Python ayarları
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# 3) Container içindeki çalışma klasörü
WORKDIR /app

# 4) Önce SADECE paket listesini kopyala ve paketleri kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5) Sonra kodu kopyala
COPY src/ src/
COPY app/ app/

# 6) Container başlayınca varsayılan olarak Streamlit'i aç
EXPOSE 8501
CMD ["streamlit", "run", "app/app.py", "--server.address=0.0.0.0", "--server.port=8501"]