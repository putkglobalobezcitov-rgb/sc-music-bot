import asyncio
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import requests
import yt_dlp
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES, PROXY_URL

logger = logging.getLogger(__name__)

# Регулярные выражения для поддерживаемых сервисов
URL_REGEX = re.compile(
    r"https?://(?:www\.|m\.)?(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?",
    re.IGNORECASE,
)


def extract_media_url(text: str) -> Optional[str]:
    """Извлекает и нормализует ссылку из сообщения."""
    match = URL_REGEX.search(text)
    if not match:
        return None
    url = match.group(0).strip(".,!?:;\"'()[]{}<>")
    
    # Разыменовываем короткие ссылки (on.soundcloud.com, vm.tiktok.com, vt.tiktok.com, youtu.be)
    if any(domain in url for domain in ["on.soundcloud.com", "vm.tiktok.com", "vt.tiktok.com"]):
        try:
            resp = requests.get(url, allow_redirects=False, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code in (301, 302, 303, 307, 308) and "Location" in resp.headers:
                loc = resp.headers["Location"]
                return loc.split("?")[0]
        except Exception as e:
            logger.warning(f"Не удалось развернуть короткую ссылку {url}: {e}")
            
    return url


def is_audio_source(url: str) -> bool:
    """Определяет, является ли источник преимущественно аудио (SoundCloud)."""
    return "soundcloud.com" in url


def get_ffmpeg_path() -> Optional[str]:
    """Возвращает путь к исполняемому файлу ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        logger.warning(f"imageio-ffmpeg не найден: {e}")
        return None


@dataclass
class DownloadedMedia:
    file_path: Path
    is_video: bool
    is_audio: bool
    title: str
    performer: str
    duration: int
    thumbnail_path: Optional[Path] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: int = 0

    def cleanup(self):
        """Удаляет временные файлы."""
        try:
            if self.file_path and self.file_path.exists():
                self.file_path.unlink(missing_ok=True)
            if self.thumbnail_path and self.thumbnail_path.exists():
                self.thumbnail_path.unlink(missing_ok=True)
            logger.info(f"Временные файлы для '{self.title}' очищены.")
        except Exception as e:
            logger.error(f"Ошибка при очистке временных файлов: {e}")


def _download_sync(url: str, output_dir: Path) -> DownloadedMedia:
    """Синхронная функция скачивания через yt-dlp."""
    unique_id = uuid.uuid4().hex[:10]
    out_template = str(output_dir / f"{unique_id}.%(ext)s")
    ffmpeg_exe = get_ffmpeg_path()
    audio_only = is_audio_source(url)

    if audio_only:
        # Для SoundCloud и аудио — конвертируем в 320kbps MP3
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'quiet': True,
            'no_warnings': True,
            'windowsfilenames': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                },
            ],
        }
    else:
        # Для TikTok, YouTube, Reels, Pinterest — скачиваем MP4 видео до 50 МБ
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][filesize<?48M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<?48M]/best[filesize<?48M]/best',
            'outtmpl': out_template,
            'quiet': True,
            'no_warnings': True,
            'windowsfilenames': True,
            'merge_output_format': 'mp4',
        }

    if ffmpeg_exe:
        ydl_opts['ffmpeg_location'] = ffmpeg_exe

    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Не удалось извлечь медиа по указанной ссылке.")

        if 'entries' in info and info['entries']:
            info = info['entries'][0]

        title = info.get('title') or "Media"
        performer = info.get('artist') or info.get('uploader') or info.get('channel') or "Downloader"
        duration = int(info.get('duration') or 0)
        thumbnail_url = info.get('thumbnail')
        width = info.get('width')
        height = info.get('height')

        # Поиск итогового файла
        matched_files = list(output_dir.glob(f"{unique_id}.*"))
        valid_files = [f for f in matched_files if not f.name.endswith(('.part', '.ytdl', '_thumb.jpg', '_thumb.png'))]
        
        if not valid_files:
            raise FileNotFoundError("Скачанный файл не найден на диске.")

        final_file = valid_files[0]
        file_size = final_file.stat().st_size

        if file_size > MAX_FILE_SIZE_BYTES:
            final_file.unlink(missing_ok=True)
            raise ValueError(f"Размер файла ({file_size / (1024 * 1024):.1f} МБ) превышает лимит Telegram (50 МБ).")

        ext = final_file.suffix.lower()
        is_audio = ext in ('.mp3', '.m4a', '.ogg', '.wav', '.flac', '.aac')
        is_video = ext in ('.mp4', '.mov', '.webm', '.mkv', '.avi')

        # Скачиваем обложку (для MP3 или превью видео)
        thumb_path = None
        if thumbnail_url:
            try:
                thumb_file = output_dir / f"{unique_id}_thumb.jpg"
                resp = requests.get(thumbnail_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    with open(thumb_file, 'wb') as f:
                        f.write(resp.content)
                    thumb_path = thumb_file
            except Exception as e:
                logger.warning(f"Не удалось сохранить превью: {e}")

        return DownloadedMedia(
            file_path=final_file,
            is_video=is_video,
            is_audio=is_audio,
            title=title,
            performer=performer,
            duration=duration,
            thumbnail_path=thumb_path,
            width=width,
            height=height,
            file_size=file_size,
        )


async def download_media(url: str) -> DownloadedMedia:
    """Асинхронная обертка для скачивания любого медиа."""
    return await asyncio.to_thread(_download_sync, url, DOWNLOAD_DIR)
