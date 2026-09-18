import asyncio
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import yt_dlp
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_BYTES, PROXY_URL

logger = logging.getLogger(__name__)

# Регулярное выражение для поиска ссылок на SoundCloud
SC_URL_PATTERN = re.compile(
    r"https?://(?:www\.|m\.)?(?:soundcloud\.com/[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+|on\.soundcloud\.com/[a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)


def extract_soundcloud_url(text: str) -> Optional[str]:
    """Извлекает ссылку SoundCloud из текста сообщения."""
    match = SC_URL_PATTERN.search(text)
    return match.group(0) if match else None


def get_ffmpeg_path() -> Optional[str]:
    """Возвращает путь к исполняемому файлу ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        logger.warning(f"Не удалось получить ffmpeg из imageio-ffmpeg: {e}")
        return None


@dataclass
class DownloadedTrack:
    file_path: Path
    title: str
    performer: str
    duration: int
    thumbnail_path: Optional[Path] = None
    file_size: int = 0

    def cleanup(self):
        """Удаляет временные файлы аудио и обложки."""
        try:
            if self.file_path and self.file_path.exists():
                self.file_path.unlink(missing_ok=True)
            if self.thumbnail_path and self.thumbnail_path.exists():
                self.thumbnail_path.unlink(missing_ok=True)
            logger.info(f"Временные файлы для '{self.title}' удалены.")
        except Exception as e:
            logger.error(f"Ошибка при очистке временных файлов: {e}")


def _download_track_sync(url: str, output_dir: Path) -> DownloadedTrack:
    """Синхронная функция скачивания через yt-dlp."""
    unique_id = uuid.uuid4().hex[:10]
    out_template = str(output_dir / f"{unique_id}_%(title).100s.%(ext)s")
    ffmpeg_exe = get_ffmpeg_path()

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
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

    if ffmpeg_exe:
        ydl_opts['ffmpeg_location'] = ffmpeg_exe

    if PROXY_URL:
        ydl_opts['proxy'] = PROXY_URL

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Извлекаем информацию и скачиваем
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Не удалось получить информацию о треке.")

        # Если передан плейлист, берем первый трек
        if 'entries' in info and info['entries']:
            info = info['entries'][0]

        title = info.get('title') or "SoundCloud Track"
        performer = info.get('artist') or info.get('uploader') or "SoundCloud"
        duration = int(info.get('duration') or 0)
        thumbnail_url = info.get('thumbnail')

        # Определяем итоговый путь к MP3-файлу
        # yt-dlp после постпроцессинга меняет расширение на .mp3
        expected_filename = ydl.prepare_filename(info)
        base_path = Path(expected_filename)
        mp3_path = base_path.with_suffix('.mp3')

        # Если файл с .mp3 не найден, ищем файл с префиксом unique_id в output_dir
        if not mp3_path.exists():
            matched_files = list(output_dir.glob(f"{unique_id}_*.mp3"))
            if matched_files:
                mp3_path = matched_files[0]
            else:
                # Возможно, расширение осталось исходным (m4a, opus, etc.)
                matched_files = list(output_dir.glob(f"{unique_id}_*.*"))
                if matched_files:
                    mp3_path = matched_files[0]
                else:
                    raise FileNotFoundError("Не удалось найти скачанный аудиофайл.")

        file_size = mp3_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            mp3_path.unlink(missing_ok=True)
            raise ValueError(
                f"Размер трека ({file_size / (1024 * 1024):.1f} МБ) превышает лимит Telegram (50 МБ)."
            )

        # Скачиваем обложку, если доступна
        thumb_path = None
        if thumbnail_url:
            try:
                thumb_file = output_dir / f"{unique_id}_thumb.jpg"
                resp = requests.get(thumbnail_url, timeout=10)
                if resp.status_code == 200:
                    with open(thumb_file, 'wb') as f:
                        f.write(resp.content)
                    thumb_path = thumb_file
            except Exception as e:
                logger.warning(f"Не удалось сохранить обложку: {e}")

        return DownloadedTrack(
            file_path=mp3_path,
            title=title,
            performer=performer,
            duration=duration,
            thumbnail_path=thumb_path,
            file_size=file_size,
        )


async def download_track(url: str) -> DownloadedTrack:
    """Асинхронная обертка для скачивания трека в фоновом потоке."""
    return await asyncio.to_thread(_download_track_sync, url, DOWNLOAD_DIR)
