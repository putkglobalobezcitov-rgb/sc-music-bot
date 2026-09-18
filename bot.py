import sys
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message

from config import BOT_TOKEN, PROXY_URL
from downloader import download_track, extract_soundcloud_url

# Принудительно устанавливаем UTF-8 для вывода в консоль Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Веб-сервер для поддержки бесплатного тарифа Render Web Service
async def health_handler(request):
    return web.Response(text="SoundCloud Music Bot is LIVE!", status=200)

async def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/healthz", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Веб-сервер для Render запущен на порту {port}")

# Инициализация бота и диспетчера с поддержкой прокси при необходимости
session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    welcome_text = (
        "👋 <b>Привет!</b>\n\n"
        "Я помогу скачать любой трек из <b>SoundCloud</b> в максимальном качестве!\n\n"
        "🎵 <b>Как пользоваться:</b>\n"
        "Просто отправь мне ссылку на трек (поддерживаются ссылки вида <code>soundcloud.com/...</code> или мобильные <code>on.soundcloud.com/...</code>).\n\n"
        "🎧 Я пришлю аудиофайл с оригинальными тегами и обложкой прямо в чат."
    )
    await message.answer(welcome_text)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    help_text = (
        "ℹ️ <b>Помощь по использованию бота:</b>\n\n"
        "1. Откройте нужный трек в SoundCloud (в браузере или приложении).\n"
        "2. Нажмите «Поделиться» (Share) и скопируйте ссылку.\n"
        "3. Отправьте ссылку сюда в чат.\n\n"
        "Бот автоматически извлечет аудиопоток наилучшего качества, конвертирует в MP3 (до 320 kbps), добавит теги с исполнителем и обложкой."
    )
    await message.answer(help_text)


@dp.message(F.text)
async def handle_message(message: Message):
    """Обработчик текстовых сообщений со ссылками."""
    text = message.text.strip()
    url = extract_soundcloud_url(text)

    if not url:
        await message.answer(
            "⚠️ Пожалуйста, отправьте корректную ссылку на трек из <b>SoundCloud</b>.\n"
            "<i>Пример: https://soundcloud.com/artist/track</i>"
        )
        return

    status_msg = await message.answer("🔍 <b>Получаю информацию о треке...</b>")
    track = None

    try:
        # Отправляем действие "загрузка аудио"
        await bot.send_chat_action(message.chat.id, ChatAction.RECORD_VOICE)

        # Обновляем статус
        await status_msg.edit_text("⬇️ <b>Скачиваю трек в максимальном качестве...</b>")
        
        # Скачиваем трек асинхронно
        track = await download_track(url)

        # Обновляем статус
        await status_msg.edit_text("📤 <b>Отправляю аудиофайл...</b>")
        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_VOICE)

        audio_file = FSInputFile(track.file_path)
        thumb_file = FSInputFile(track.thumbnail_path) if track.thumbnail_path else None

        # Отправляем аудиофайл в чат
        await message.answer_audio(
            audio=audio_file,
            title=track.title,
            performer=track.performer,
            duration=track.duration,
            thumbnail=thumb_file,
            caption=f"🎧 <b>{track.performer} - {track.title}</b>\n<i>Качество: 320 kbps (Best)</i>"
        )

        # Удаляем статусное сообщение после успешной отправки
        await status_msg.delete()

    except ValueError as ve:
        logger.warning(f"Ошибка валидации для {url}: {ve}")
        await status_msg.edit_text(f"⚠️ {ve}")
    except Exception as e:
        logger.error(f"Ошибка при обработке {url}: {e}", exc_info=True)
        await status_msg.edit_text(
            "❌ <b>Произошла ошибка при скачивании трека.</b>\n"
            "Возможно, трек приватный, заблокирован правообладателем или недоступен в вашем регионе."
        )
    finally:
        # Очищаем временные файлы
        if track:
            track.cleanup()


async def main():
    """Точка входа запуска бота."""
    print("====================================================")
    print("          SoundCloud Music Telegram Bot             ")
    print("====================================================")
    logger.info("Подключение к серверам Telegram...")
    try:
        # Проверяем связь с Telegram API
        me = await bot.get_me()
        logger.info(f"✅ Бот успешно авторизован: @{me.username} ({me.first_name})")
        print(f"\n>>> Бот @{me.username} ЗАПУЩЕН И ГОТОВ К РАБОТЕ! <<<")
        print(">>> Отправьте ссылку на трек SoundCloud боту в Telegram <<<\n")
        
        # Запускаем веб-сервер для Render.com
        await start_health_server()
        
        # Удаляем старые вебхуки (если были) и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        err_text = str(e)
        if "Cannot connect to host api.telegram.org" in err_text or "ClientConnectorError" in err_text or "Timeout" in err_text:
            print("\n" + "="*56)
            print("❌ ОШИБКА: НЕТ СВЯЗИ С TELEGRAM (api.telegram.org)!")
            print("="*56)
            print("Серверы Telegram Bot API заблокированы вашим провайдером.")
            print("ЧТО ДЕЛАТЬ:")
            print("1. Включите ваш VPN (например, Happ, WARP или любой другой).")
            print("2. Либо укажите адрес вашего прокси в файле .env (параметр PROXY_URL).")
            print("3. Запустите run.bat снова.")
            print("="*56 + "\n")
        else:
            logger.error(f"Непредвиденная ошибка при запуске: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
