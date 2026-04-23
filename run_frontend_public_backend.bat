@echo off
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Missing Python runtime: %PYTHON_EXE%
    echo Create the backend virtual environment first.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8765/' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if "%ERRORLEVEL%"=="0" (
    echo Frontend is already responding at http://127.0.0.1:8765/
    echo Stop the current frontend window before starting the public-backend frontend.
    pause
    exit /b 0
)

set /p "BACKEND_PUBLIC_URL=Enter the backend public URL (https://...): "
if not defined BACKEND_PUBLIC_URL (
    echo No backend public URL was provided.
    pause
    exit /b 1
)

if "!BACKEND_PUBLIC_URL:~-1!"=="/" set "BACKEND_PUBLIC_URL=!BACKEND_PUBLIC_URL:~0,-1!"

set "BACKEND_URL=!BACKEND_PUBLIC_URL!"
set "BACKEND_WS_URL=!BACKEND_PUBLIC_URL:https://=wss://!"
set "BACKEND_WS_URL=!BACKEND_WS_URL:http://=ws://!"

cd /d "%ROOT%frontend"
"%PYTHON_EXE%" run_frontend.py run app.py --host 127.0.0.1 --port 8765
