@echo off
setlocal enabledelayedexpansion

REM Builds a distributable Windows installer (Setup EXE) using Inno Setup.
REM Prereq:
REM 1) Python, npm, uv installed
REM 2) Inno Setup 6 installed (iscc.exe available)

set "ROOT=%~dp0.."
set "STAGING=%ROOT%\installer\staging"
set "DIST=%ROOT%\installer\dist"

pushd "%ROOT%" || (
  echo [ERROR] Unable to locate repository root.
  exit /b 1
)

echo [1/8] Building backend executable + dashboard...
call "%ROOT%\scripts\windows_build_backend.bat"
if errorlevel 1 goto :fail

echo [2/8] Checking Inno Setup compiler (iscc)...
where iscc >nul 2>nul
if errorlevel 1 (
  echo [ERROR] iscc.exe not found.
  echo [INFO] Install Inno Setup 6 and ensure ISCC is in PATH.
  echo [INFO] Download: https://jrsoftware.org/isinfo.php
  goto :fail
)

echo [3/8] Preparing installer staging folders...
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%" || goto :fail
if not exist "%DIST%" mkdir "%DIST%" || goto :fail

echo [4/8] Copying backend bundle...
robocopy "%ROOT%\backend\dist\backend" "%STAGING%\backend\dist\backend" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [5/8] Copying dashboard build...
robocopy "%ROOT%\web_dashboard_ui\dist" "%STAGING%\web_dashboard_ui\dist" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [6/8] Copying runtime defaults and models...
if exist "%ROOT%\.env" (
  copy /Y "%ROOT%\.env" "%STAGING%\.env" >nul || goto :fail
) else if exist "%ROOT%\.env.example" (
  copy /Y "%ROOT%\.env.example" "%STAGING%\.env" >nul || goto :fail
)

if exist "%ROOT%\backend\storage\models" (
  robocopy "%ROOT%\backend\storage\models" "%STAGING%\backend\storage\models" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 goto :fail
)

if not exist "%STAGING%\backend\storage\snapshots" mkdir "%STAGING%\backend\storage\snapshots"
if not exist "%STAGING%\backend\storage\logs" mkdir "%STAGING%\backend\storage\logs"
if not exist "%STAGING%\backend\storage\backups" mkdir "%STAGING%\backend\storage\backups"

if exist "%ROOT%\installer\prereqs" (
  echo [INFO] Copying optional prerequisite installers...
  robocopy "%ROOT%\installer\prereqs" "%STAGING%\prereqs" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 goto :fail
)

echo [7/8] Writing launcher scripts...
(
  echo @echo off
  echo setlocal
  echo set "APP_DIR=%%~dp0"
  echo start "Thesis Backend" "%%APP_DIR%%backend\dist\backend\backend.exe"
  echo powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='http://127.0.0.1:8765/health'; $ok=$false; for($i=0; $i -lt 30; $i^++){ try { Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 2 ^| Out-Null; $ok=$true; break } catch {}; Start-Sleep -Milliseconds 500 }; if(-not $ok){ Start-Sleep -Seconds 2 }" ^>nul 2^>^&1
  echo start "" "http://127.0.0.1:8765/dashboard"
  echo endlocal
) > "%STAGING%\run_thesis_monitor.bat"

(
  echo @echo off
  echo taskkill /F /IM backend.exe /T ^>nul 2^>^&1
) > "%STAGING%\stop_thesis_monitor.bat"

echo [8/8] Building installer setup EXE...
iscc "%ROOT%\scripts\windows_installer.iss" /DSourceRoot="%ROOT%"
if errorlevel 1 goto :fail

echo.
echo [OK] Installer build complete.
echo Output: %DIST%\ThesisMonitorSetup.exe
popd
exit /b 0

:fail
echo.
echo [ERROR] Windows installer build failed.
popd
exit /b 1
