@echo off
title VidDrop - YouTube İndirici
color 0a
echo.
echo  VidDrop baslatiliyor...
echo.

cd /d "%~dp0"
start "" python app.py
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5000"

echo  Site acildi! Bu pencereyi kapatmayin.
echo  Kapatmak icin bu pencereyi kapatin.
pause >nul
