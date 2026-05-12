# Windows Local Startup and Installer

## Development Flow

1. Build dashboard assets:

```bash
cd web_dashboard_ui
npm install
npm run build
```

2. Start backend:

```bash
cd <repo-root>
python backend/run_backend.py
```

3. Open local dashboard in browser:

- `http://127.0.0.1:8765/dashboard`

## GitHub Actions Portable Build

Pushing to `main` runs `.github/workflows/build-windows.yml` and uploads the
portable `CondoGuardian-Windows` artifact. Extract the full folder and run:

```text
CondoGuardian.exe
```

The portable build starts the backend and opens:

```text
http://127.0.0.1:8765/dashboard
```

## Full Offline Installer Release

For demos and non-technical installs, use the Inno Setup installer:

```text
IntruFlare-Setup-v2.2.0.exe
```

The installer copies app files to:

```text
%LOCALAPPDATA%\Programs\IntruFlare
```

Runtime data is stored outside the app folder so reinstalls do not wipe local data:

```text
%LOCALAPPDATA%\CondoGuardian
```

The packaged app automatically defaults to these runtime paths:

```text
%LOCALAPPDATA%\CondoGuardian\system.db
%LOCALAPPDATA%\CondoGuardian\snapshots
%LOCALAPPDATA%\CondoGuardian\logs
%LOCALAPPDATA%\CondoGuardian\face_samples
%LOCALAPPDATA%\CondoGuardian\models
```

## AI Model Pack

Do not commit AI model files to git. Upload this model pack as a GitHub Release
asset instead:

```text
IntruFlare-AI-Models-v2.2.0.zip
```

The ZIP root must contain:

```text
fire/
  yolov8s_fire_smoke_hardneg.onnx
insightface/
  models/
    buffalo_l/
      det_10g.onnx
      w600k_r50.onnx
      1k3d68.onnx
      2d106det.onnx
      genderage.onnx
```

Manual fallback extraction target:

```text
%LOCALAPPDATA%\CondoGuardian\models
```

Expected files after extraction:

```text
%LOCALAPPDATA%\CondoGuardian\models\fire\yolov8s_fire_smoke_hardneg.onnx
%LOCALAPPDATA%\CondoGuardian\models\insightface\models\buffalo_l\det_10g.onnx
%LOCALAPPDATA%\CondoGuardian\models\insightface\models\buffalo_l\w600k_r50.onnx
```

To build the model pack on Windows, stage only deployable ONNX files:

```powershell
$stage = "$env:TEMP\IntruFlare-AI-Models-v2.2.0"
Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$stage\fire" | Out-Null
New-Item -ItemType Directory -Force -Path "$stage\insightface\models\buffalo_l" | Out-Null

Copy-Item "C:\path\to\best.onnx" "$stage\fire\yolov8s_fire_smoke_hardneg.onnx"
Copy-Item "C:\path\to\buffalo_l\*.onnx" "$stage\insightface\models\buffalo_l\"

Compress-Archive -Path "$stage\*" -DestinationPath ".\IntruFlare-AI-Models-v2.2.0.zip" -Force
```

Do not include `.pt` training weights, training images, result CSV files, local
databases, or snapshots in the model pack.

## GitHub Installer Workflow

Before building the installer, create or edit release `v2.2.0` and upload:

```text
IntruFlare-AI-Models-v2.2.0.zip
```

Then run GitHub Actions manually:

```text
Actions -> Build Windows EXE -> Run workflow
```

Use these inputs:

```text
build_installer: true
model_release_tag: v2.2.0
model_asset_name: IntruFlare-AI-Models-v2.2.0.zip
upload_installer_to_release: true
```

The workflow downloads the model pack, verifies required ONNX files, builds:

```text
IntruFlare-Setup-v2.2.0.exe
```

and uploads it as both a workflow artifact and a release asset when requested.

## Local Installer Build

Run on a Windows machine:

```bash
set MODEL_PACK_ZIP=C:\path\to\IntruFlare-AI-Models-v2.2.0.zip
scripts\windows_build_installer.bat
```

Output:

- `installer/dist/IntruFlare-Setup-v2.2.0.exe`

## Runtime Layout Requirements

- Source/development runs can use `backend/storage/models`.
- Portable EXE and installed builds use `%LOCALAPPDATA%\CondoGuardian\models` by default.
- Optional installed runtime overrides can be placed in `%LOCALAPPDATA%\CondoGuardian\.env`.

## Runtime Behavior

- `CondoGuardian.exe` starts the FastAPI backend.
- Dashboard is served by the backend at `/dashboard`.
- Browser is the primary UI surface on Windows.
- Windows Firewall should allow private-network access so phones and ESP32 nodes can reach the backend.
