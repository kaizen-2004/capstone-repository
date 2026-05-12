@echo off
setlocal enabledelayedexpansion

REM Builds the IntruFlare Windows installer using Inno Setup.
REM Optional: set MODEL_PACK_ZIP=C:\path\to\IntruFlare-AI-Models-v2.2.0.zip

set "ROOT=%~dp0.."
set "STAGING=%ROOT%\installer\staging"
set "DIST=%ROOT%\installer\dist"
set "VERSION=2.2.0"

pushd "%ROOT%" || (
  echo [ERROR] Unable to locate repository root.
  exit /b 1
)

echo [1/7] Building desktop executable + dashboard...
call "%ROOT%\scripts\windows_build_backend.bat"
if errorlevel 1 goto :fail

echo [2/7] Checking Inno Setup compiler (iscc)...
where iscc >nul 2>nul
if errorlevel 1 (
  echo [ERROR] iscc.exe not found.
  echo [INFO] Install Inno Setup 6 and ensure ISCC is in PATH.
  echo [INFO] Download: https://jrsoftware.org/isinfo.php
  goto :fail
)

echo [3/7] Preparing installer staging folders...
if exist "%STAGING%" rmdir /s /q "%STAGING%"
mkdir "%STAGING%\app" || goto :fail
mkdir "%STAGING%\models" || goto :fail
mkdir "%STAGING%\prereqs" || goto :fail
if not exist "%DIST%" mkdir "%DIST%" || goto :fail

echo [4/7] Copying desktop executable bundle...
robocopy "%ROOT%\dist\CondoGuardian" "%STAGING%\app" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [5/7] Staging AI models...
if defined MODEL_PACK_ZIP (
  if not exist "%MODEL_PACK_ZIP%" (
    echo [ERROR] MODEL_PACK_ZIP not found: %MODEL_PACK_ZIP%
    goto :fail
  )
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path $env:MODEL_PACK_ZIP -DestinationPath '%STAGING%\models' -Force" || goto :fail
) else if exist "%ROOT%\backend\storage\models" (
  robocopy "%ROOT%\backend\storage\models" "%STAGING%\models" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 goto :fail
) else (
  echo [ERROR] No MODEL_PACK_ZIP or backend\storage\models found.
  echo [INFO] The full offline installer requires bundled AI models.
  goto :fail
)

if exist "%ROOT%\installer\prereqs" (
  echo [INFO] Copying optional prerequisite installers...
  robocopy "%ROOT%\installer\prereqs" "%STAGING%\prereqs" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 goto :fail
)

echo [6/7] Validating staged app bundle...
if not exist "%STAGING%\app\CondoGuardian.exe" (
  echo [ERROR] Staged app is missing CondoGuardian.exe.
  goto :fail
)
if not exist "%STAGING%\models\fire\yolov8s_fire_smoke_hardneg.onnx" (
  echo [ERROR] Staged model pack is missing fire\yolov8s_fire_smoke_hardneg.onnx.
  goto :fail
)
if not exist "%STAGING%\models\insightface\models\buffalo_l\det_10g.onnx" (
  echo [ERROR] Staged model pack is missing insightface\models\buffalo_l\det_10g.onnx.
  goto :fail
)
if not exist "%STAGING%\models\insightface\models\buffalo_l\w600k_r50.onnx" (
  echo [ERROR] Staged model pack is missing insightface\models\buffalo_l\w600k_r50.onnx.
  goto :fail
)

echo [7/7] Building installer setup EXE...
iscc "%ROOT%\scripts\windows_installer.iss" /DSourceRoot="%ROOT%" /DMyAppVersion="%VERSION%"
if errorlevel 1 goto :fail

echo.
echo [OK] Installer build complete.
echo Output: %DIST%\IntruFlare-Setup-v%VERSION%.exe
popd
exit /b 0

:fail
echo.
echo [ERROR] Windows installer build failed.
popd
exit /b 1
