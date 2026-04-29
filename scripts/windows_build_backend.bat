@echo off
setlocal enabledelayedexpansion

REM Build Windows backend executable + dashboard assets.
REM Usage: run from anywhere: scripts\windows_build_backend.bat

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
uv sync || goto :uv_fallback
goto :deps_done

:uv_fallback
echo [WARN] uv sync failed, falling back to requirements.txt...
uv pip install -r requirements.txt || goto :fail

:deps_done
echo [4/7] Building dashboard...
pushd web_dashboard_ui || goto :fail
npm install || goto :fail
npm run build || goto :fail
popd

echo [5/7] Ensuring .env exists...
if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul || goto :fail
    echo [INFO] Created .env from .env.example. Please review values.
  ) else (
    echo [WARN] .env.example not found. Create .env manually before runtime.
  )
)

echo [6/7] Installing PyInstaller...
uv pip install pyinstaller || goto :fail

echo [7/7] Packaging backend executable...
uv run python -m PyInstaller backend/run_backend.py --name backend --onedir --clean --noconfirm --distpath backend/dist --workpath backend/build --specpath backend --paths . --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on || goto :fail

echo.
echo [OK] Build complete.
echo Executable: backend\dist\backend\backend.exe
echo Dashboard:  http://127.0.0.1:8765/dashboard
echo.
echo To run now:
echo   backend\dist\backend\backend.exe

popd
exit /b 0

:fail
echo.
echo [ERROR] Build failed. See logs above.
popd
exit /b 1
