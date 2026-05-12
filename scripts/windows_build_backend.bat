@echo off
setlocal enabledelayedexpansion

REM Build the Windows desktop executable + bundled dashboard assets.
REM Usage: run from repo root or anywhere: scripts\windows_build_backend.bat

set "ROOT=%~dp0.."
pushd "%ROOT%" || (
  echo [ERROR] Unable to locate repository root.
  exit /b 1
)

echo [1/7] Checking required tools...
where python >nul 2>nul || (
  echo [ERROR] Python is not installed or not in PATH.
  popd
  exit /b 1
)
where npm >nul 2>nul || (
  echo [ERROR] npm is not installed or not in PATH.
  popd
  exit /b 1
)

echo [2/7] Ensuring uv is installed...
where uv >nul 2>nul
if errorlevel 1 (
  python -m pip install --upgrade pip || goto :fail
  python -m pip install uv || goto :fail
)

echo [3/7] Installing backend dependencies via uv...
if not exist ".venv\Scripts\python.exe" (
  uv venv .venv || goto :fail
)
uv pip install --python ".venv\Scripts\python.exe" -r requirements.txt || goto :fail

echo [4/7] Building dashboard assets...
pushd web_dashboard_ui || goto :fail
if exist package-lock.json (
  npm ci || goto :fail
) else (
  npm install || goto :fail
)
npm run build || goto :fail
popd

if exist "backend\web_dist" rmdir /s /q "backend\web_dist"
mkdir "backend\web_dist" || goto :fail
xcopy "web_dashboard_ui\dist\*" "backend\web_dist\" /E /I /Y >nul || goto :fail

echo [5/7] Installing PyInstaller...
uv pip install --python ".venv\Scripts\python.exe" pyinstaller || goto :fail

echo [6/7] Checking external model bundle expectation...
echo [INFO] Portable builds do not include AI models by default.
echo [INFO] Put models in %%LOCALAPPDATA%%\CondoGuardian\models or use the installer workflow.

echo [7/7] Packaging CondoGuardian executable...
set PYI_ARGS=--noconfirm --clean --onedir --name CondoGuardian --console --add-data "backend\web_dist;web_dist" --collect-all cv2 --hidden-import uvicorn.logging --hidden-import uvicorn.loops --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols --hidden-import uvicorn.protocols.http --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan --hidden-import uvicorn.lifespan.on
if exist "tools\ffmpeg.exe" set PYI_ARGS=!PYI_ARGS! --add-binary "tools\ffmpeg.exe;tools"
".venv\Scripts\python.exe" -m PyInstaller !PYI_ARGS! desktop_launcher.py || goto :fail

if not exist "dist\CondoGuardian\CondoGuardian.exe" (
  echo [ERROR] dist\CondoGuardian\CondoGuardian.exe was not created.
  goto :fail
)

echo.
echo [OK] Build complete.
echo Executable: dist\CondoGuardian\CondoGuardian.exe
echo Dashboard:  http://127.0.0.1:8765/dashboard
echo.
echo To run now:
echo   dist\CondoGuardian\CondoGuardian.exe

popd
exit /b 0

:fail
echo.
echo [ERROR] Build failed. See logs above.
popd
exit /b 1
