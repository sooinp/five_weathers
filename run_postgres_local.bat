@echo off
setlocal

set "ROOT=%~dp0"
set "PG_BIN=C:\Program Files\PostgreSQL\16\bin"
set "PGDATA=%ROOT%backend\.pgdata"
set "PWFILE=%ROOT%backend\.pgpass_init.txt"
set "PGPORT=55432"

if not exist "%PG_BIN%\postgres.exe" (
    echo PostgreSQL 16 binaries were not found at:
    echo   %PG_BIN%
    echo Install PostgreSQL 16 first, then run this file again.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $tcp = New-Object Net.Sockets.TcpClient; $iar = $tcp.BeginConnect('127.0.0.1', %PGPORT%, $null, $null); if ($iar.AsyncWaitHandle.WaitOne(1500, $false)) { $tcp.EndConnect($iar); $tcp.Close(); exit 0 } else { $tcp.Close(); exit 1 } } catch { exit 1 }"
if "%ERRORLEVEL%"=="0" (
    echo Local project PostgreSQL is already running on 127.0.0.1:%PGPORT%.
    pause
    exit /b 0
)

if not exist "%PGDATA%\PG_VERSION" (
    echo Initializing local project PostgreSQL cluster at:
    echo   %PGDATA%
    if not exist "%PGDATA%" mkdir "%PGDATA%"
    >"%PWFILE%" <nul set /p ="password"
    "%PG_BIN%\initdb.exe" -D "%PGDATA%" -U postgres -A scram-sha-256 --pwfile="%PWFILE%" --encoding=UTF8 --locale=C
)

echo Starting local project PostgreSQL on 127.0.0.1:%PGPORT%
echo Keep this window open while the backend is running.
"%PG_BIN%\postgres.exe" -D "%PGDATA%" -p %PGPORT% -c listen_addresses=127.0.0.1
