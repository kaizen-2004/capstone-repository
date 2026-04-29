@echo off
setlocal enabledelayedexpansion

REM Installer-style setup for Windows local app launcher.
REM This installs runtime files to %LOCALAPPDATA%\ThesisMonitor and creates a Desktop shortcut.

set "ROOT=%~dp0.."
set "APP_HOME=%LOCALAPPDATA%\ThesisMonitor"
set "SHORTCUT=%USERPROFILE%\Desktop\Thesis Monitor.lnk"

echo [INFO] Repo root: %ROOT%

if not exist "%ROOT%\backend\dist\backend\backend.exe" (
  echo [ERROR] backend.exe not found.
  echo [INFO] Build first with scripts\windows_build_backend.bat
  exit /b 1
)

if not exist "%ROOT%\web_dashboard_ui\dist\index.html" (
  echo [ERROR] Dashboard build not found.
  echo [INFO] Build first with scripts\windows_build_backend.bat
  exit /b 1
)

echo [1/5] Preparing install directory...
if exist "%APP_HOME%" rmdir /s /q "%APP_HOME%"
mkdir "%APP_HOME%" || goto :fail

echo [2/5] Copying backend executable bundle...
robocopy "%ROOT%\backend\dist\backend" "%APP_HOME%\backend\dist\backend" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [3/5] Copying dashboard build...
robocopy "%ROOT%\web_dashboard_ui\dist" "%APP_HOME%\web_dashboard_ui\dist" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [4/5] Copying runtime config and model assets...
if exist "%ROOT%\.env" copy /Y "%ROOT%\.env" "%APP_HOME%\.env" >nul
if exist "%ROOT%\backend\storage\models" (
  robocopy "%ROOT%\backend\storage\models" "%APP_HOME%\backend\storage\models" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 goto :fail
)

if not exist "%APP_HOME%\backend\storage\snapshots" mkdir "%APP_HOME%\backend\storage\snapshots"
if not exist "%APP_HOME%\backend\storage\logs" mkdir "%APP_HOME%\backend\storage\logs"

echo [5/5] Creating launcher and desktop shortcut...
(
  echo @echo off
  echo setlocal
  echo set "APP_DIR=%%~dp0"
  echo start "Thesis Backend" "%%APP_DIR%%backend\dist\backend\backend.exe"
  echo timeout /t 3 /nobreak ^>nul
  echo start "" "http://127.0.0.1:8765/dashboard"
  echo endlocal
) > "%APP_HOME%\run_thesis_monitor.bat"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$W=New-Object -ComObject WScript.Shell; $S=$W.CreateShortcut('%SHORTCUT%'); $S.TargetPath='%APP_HOME%\run_thesis_monitor.bat'; $S.WorkingDirectory='%APP_HOME%'; $S.IconLocation='%APP_HOME%\backend\dist\backend\backend.exe,0'; $S.Description='Launch Thesis Monitor'; $S.Save()" || goto :fail

echo.
echo [OK] Installed to: %APP_HOME%
echo [OK] Desktop shortcut created: %SHORTCUT%
echo [INFO] Double-click "Thesis Monitor" on Desktop to launch.
exit /b 0

:fail
echo.
echo [ERROR] Install failed.
exit /b 1
