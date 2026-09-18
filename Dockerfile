FROM python:3.12-slim

# Установка ffmpeg для обработки аудио
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Порт для веб-сервера Render
EXPOSE 8080

CMD ["python", "bot.py"]
