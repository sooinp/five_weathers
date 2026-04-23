@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%backend\.venv\Scripts\python.exe"
set "LOCAL_DB_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/postgres"

if not exist "%PYTHON_EXE%" (
    echo Missing Python runtime: %PYTHON_EXE%
    echo Create the backend virtual environment first.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $tcp = New-Object Net.Sockets.TcpClient; $iar = $tcp.BeginConnect('127.0.0.1', 55432, $null, $null); if ($iar.AsyncWaitHandle.WaitOne(1500, $false)) { $tcp.EndConnect($iar); $tcp.Close(); exit 0 } else { $tcp.Close(); exit 1 } } catch { exit 1 }"
if not "%ERRORLEVEL%"=="0" (
    echo Local project PostgreSQL is not responding on 127.0.0.1:55432.
    echo Starting a dedicated DB window...
    start "Fiveweathers Local DB" "%ROOT%run_postgres_local.bat"
    timeout /t 5 /nobreak >nul
    powershell -NoProfile -Command "try { $tcp = New-Object Net.Sockets.TcpClient; $iar = $tcp.BeginConnect('127.0.0.1', 55432, $null, $null); if ($iar.AsyncWaitHandle.WaitOne(1500, $false)) { $tcp.EndConnect($iar); $tcp.Close(); exit 0 } else { $tcp.Close(); exit 1 } } catch { exit 1 }"
    if not "%ERRORLEVEL%"=="0" (
        echo Failed to reach the local project DB.
        echo Keep the "Fiveweathers Local DB" window open, then run this file again.
        pause
        exit /b 1
    )
)

powershell -NoProfile -Command "try { $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/' -TimeoutSec 3; if ($resp.message -eq 'Backend is running') { exit 0 } else { exit 1 } } catch { exit 1 }"
if "%ERRORLEVEL%"=="0" (
    echo Backend is already responding at http://127.0.0.1:8000/
    pause
    exit /b 0
)

cd /d "%ROOT%backend"
set "DATABASE_URL=%LOCAL_DB_URL%"
"%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
