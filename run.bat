@echo off
chcp 65001 > nul
title SoundCloud Music Telegram Bot
echo ====================================================
echo        SoundCloud Telegram Downloader Bot
echo ====================================================
echo.
echo Проверка зависимостей...
python -m pip install -r requirements.txt
echo.
echo Запуск бота...
python bot.py
pause
