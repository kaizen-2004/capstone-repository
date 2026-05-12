@echo off
setlocal

REM Run packaged desktop app and open dashboard in browser.
REM Usage: scripts\windows_run_backend.bat

set "ROOT=%~dp0.."
set "EXE=%ROOT%\dist\CondoGuardian\CondoGuardian.exe"
set "DASHBOARD_URL=http://127.0.0.1:8765/dashboard"

if not exist "%EXE%" (
  echo [ERROR] Packaged app not found:
  echo         %EXE%
  echo [INFO] Build first with scripts\windows_build_backend.bat
  exit /b 1
)

echo [INFO] Starting IntruFlare...
start "IntruFlare" "%EXE%"

echo [INFO] Waiting for backend to initialize...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='%DASHBOARD_URL%'; for($i=0; $i -lt 30; $i++){ try { Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 2 | Out-Null; exit 0 } catch {}; Start-Sleep -Milliseconds 500 }; exit 0" >nul 2>&1

echo [INFO] Opening dashboard in default browser...
start "" "%DASHBOARD_URL%"

echo [OK] App launch requested.
exit /b 0
