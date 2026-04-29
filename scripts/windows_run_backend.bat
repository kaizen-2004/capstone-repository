@echo off
setlocal

REM Run packaged backend and open dashboard in browser.
REM Usage: scripts\windows_run_backend.bat

set "ROOT=%~dp0.."
set "EXE=%ROOT%\backend\dist\backend\backend.exe"
set "DASHBOARD_URL=http://127.0.0.1:8765/dashboard"

if not exist "%EXE%" (
  echo [ERROR] Packaged backend not found:
  echo         %EXE%
  echo [INFO] Build first with scripts\windows_build_backend.bat
  exit /b 1
)

echo [INFO] Starting backend...
start "Thesis Backend" "%EXE%"

echo [INFO] Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

echo [INFO] Opening dashboard in default browser...
start "" "%DASHBOARD_URL%"

echo [OK] Backend launch requested.
echo If dashboard does not load yet, wait a few seconds and refresh.

exit /b 0
