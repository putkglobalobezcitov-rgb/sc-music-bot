@echo off
title Push to GitHub
cd /d "%~dp0"
echo ====================================================
echo             Pushing code to GitHub...
echo ====================================================
echo.
git push -u origin main
echo.
echo ====================================================
echo  If you see an error above, check your login/token.
echo ====================================================
pause
