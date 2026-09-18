import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError("Ошибка: Токен бота BOT_TOKEN не задан в файле .env!")

DOWNLOAD_DIR = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Опциональный прокси для Telegram API (http://..., socks5://...)
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None
