@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Missing Python runtime: %PYTHON_EXE%
    echo Create the backend virtual environment first.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/' -TimeoutSec 3; if ($resp.message -eq 'Backend is running') { exit 0 } else { exit 1 } } catch { exit 1 }"
if not "%ERRORLEVEL%"=="0" (
    echo Backend is not responding at http://127.0.0.1:8000/
    echo Run run_backend_local.bat first.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8765/' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if "%ERRORLEVEL%"=="0" (
    echo Frontend is already responding at http://127.0.0.1:8765/
    echo Open http://127.0.0.1:8765 in your browser.
    pause
    exit /b 0
)

cd /d "%ROOT%frontend"
set "BACKEND_URL=http://127.0.0.1:8000"
set "BACKEND_WS_URL=ws://127.0.0.1:8000"
"%PYTHON_EXE%" run_frontend.py run app.py --host 127.0.0.1 --port 8765
