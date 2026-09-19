import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ChatAction
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, Message

from config import BOT_TOKEN, PROXY_URL
from downloader import download_media, extract_media_url

# UTF-8 вывод для Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# Веб-сервер для поддержки Render Web Service (бесплатный тариф)
async def health_handler(request):
    return web.Response(text="Universal Downloader Bot is LIVE!", status=200)


async def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/healthz", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-check сервер запущен на порту {port}")


session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties())
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = (
        "Привет. Отправь мне ссылку (SoundCloud, TikTok, YouTube Shorts, Reels, Pinterest) — "
        "я сразу скачаю и пришлю файл без лишних кнопок."
    )
    await message.answer(welcome_text)


@dp.message(F.text)
async def handle_url(message: Message):
    text = message.text.strip()
    url = extract_media_url(text)

    if not url:
        await message.answer("Отправь ссылку на трек или видео.")
        return

    status_msg = await message.answer("Скачиваю...")
    media = None

    try:
        await bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)
        media = await download_media(url)

        thumb = FSInputFile(media.thumbnail_path) if media.thumbnail_path and media.thumbnail_path.exists() else None
        file_to_send = FSInputFile(media.file_path)

        if media.is_audio:
            await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)
            await message.answer_audio(
                audio=file_to_send,
                title=media.title,
                performer=media.performer,
                duration=media.duration,
                thumbnail=thumb,
                caption=f"{media.performer} - {media.title}"
            )
        elif media.is_video:
            await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VIDEO)
            await message.answer_video(
                video=file_to_send,
                duration=media.duration,
                width=media.width,
                height=media.height,
                thumbnail=thumb,
                caption=media.title[:1000] if media.title else None
            )
        else:
            await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
            await message.answer_document(document=file_to_send, caption=media.title)

        await status_msg.delete()

    except ValueError as ve:
        await status_msg.edit_text(f"Ошибка: {ve}")
    except Exception as e:
        logger.error(f"Ошибка скачивания {url}: {e}", exc_info=True)
        await status_msg.edit_text("Не удалось скачать. Возможно, ссылка приватная или удалена.")
    finally:
        if media:
            media.cleanup()


async def main():
    logger.info("Запуск Universal Downloader бота...")
    try:
        me = await bot.get_me()
        logger.info(f"Бот успешно авторизован: @{me.username} ({me.first_name})")
        print(f"\n>>> БОТ @{me.username} ГОТОВ К РАБОТЕ! <<<\n")
        
        await start_health_server()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
