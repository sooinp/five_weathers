@echo off
setlocal
set "NGROK_AUTHTOKEN="

where ngrok >nul 2>&1
if errorlevel 1 (
    echo ngrok command was not found in PATH.
    echo Run ngrok from the terminal where it is installed, or add it to PATH first.
    pause
    exit /b 1
)

if defined NGROK_AUTHTOKEN (
    ngrok config add-authtoken "%NGROK_AUTHTOKEN%"
)

ngrok http 127.0.0.1:8000
