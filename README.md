# Telegram-бот для скачивания музыки из SoundCloud

Бот скачивает музыку с SoundCloud в наилучшем качестве (MP3 320 kbps), извлекает обложку альбома, автора, название и длительность, а затем отправляет нативный аудиофайл прямо в чат Telegram.

## 🚀 Быстрый запуск

1. Перейдите в папку проекта:
   `C:\Users\SystemX\.gemini\antigravity-ide\scratch\sc-music-bot`
2. Запустите файл **`run.bat`** двойным кликом (или командой `python bot.py` в терминале).

---

## ⚙️ Настройки (`.env`)

Все параметры хранятся в файле `.env`:
```env
BOT_TOKEN=8646915009:AAEeof5RjcmOGo7KrUSNM1ago5u3l61nbmQ
DOWNLOAD_DIR=downloads
MAX_FILE_SIZE_MB=50

# Опционально: если у вашего провайдера заблокированы api.telegram.org или soundcloud.com:
# PROXY_URL=http://127.0.0.1:12334
# PROXY_URL=socks5://127.0.0.1:1080
```

---

## 🎧 Возможности

- **Качество**: максимальный битрейт аудио SoundCloud (конвертация и тегирование через FFmpeg в 320 kbps).
- **Поддержка любых ссылок**:
  - `https://soundcloud.com/artist/track`
  - `https://m.soundcloud.com/artist/track`
  - Мобильные короткие ссылки `https://on.soundcloud.com/...`
- **Интеграция с плеером Telegram**: вшивание названия, автора, длительности и обложки.
- **Автоочистка**: временные файлы удаляются с диска сразу после отправки.
