# Windows Desktop Startup (Tauri + FastAPI)

## Development Flow

1. Build dashboard assets:

```bash
cd web_dashboard_ui
npm install
npm run build
```

2. Start desktop shell:

```bash
cd desktop
npm install
npm run dev
```

The Tauri shell attempts to launch backend automatically and opens `/dashboard`.

## MSI Build

```bash
cd desktop
npm run build
```

Output:

- `desktop/src-tauri/target/release/bundle/msi/*.msi`

## Runtime Behavior

- App starts local backend.
- Dashboard loads from local host.
- On close, backend child process is terminated.
