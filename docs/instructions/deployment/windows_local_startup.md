# Windows Local Startup (Backend + Browser)

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

## Windows Portable Build (PyInstaller)

Run on a Windows machine:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install pyinstaller
python -m pip install fastapi "uvicorn[standard]" pydantic numpy opencv-python httpx pywebpush zeroconf python-multipart

python -m PyInstaller backend/run_backend.py --name backend --onedir --clean --noconfirm --distpath backend/dist --workpath backend/build --specpath backend --paths . --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on
```

Output:

- `backend/dist/backend/backend.exe`

## Runtime Layout Requirements

- Keep dashboard build available at `web_dashboard_ui/dist`.
- Keep model files available under `backend/storage/models`.
- Keep `.env` at project root when environment overrides are needed.

## Runtime Behavior

- Backend starts as a local process.
- Dashboard is served by the backend at `/dashboard`.
- Browser is the primary UI surface on Windows.
