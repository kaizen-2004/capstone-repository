# Desktop Shell (Tauri)

Windows desktop shell for the local-first monitoring system.

## Purpose

- Launches the local FastAPI backend automatically.
- Opens desktop webview to `http://127.0.0.1:8765/dashboard`.
- Supports MSI bundling through Tauri.

## Development

```bash
cd desktop
npm install
npm run dev
```

## Build MSI

```bash
cd desktop
npm run build
```

Generated installer output is under `desktop/src-tauri/target/release/bundle/msi/`.
