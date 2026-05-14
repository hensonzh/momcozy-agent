# Momcozy Agent Backend Deployment

This backend exposes one FastAPI service for App debugging:

```text
GET  /healthz
POST /api/ag-ui
WS   /api/ag-ui-ws
```

Use one worker for App debugging because conversation state is currently held in process memory by `ChatRuntime`.

## Environment

Copy `.env.example` to `.env` and set real values:

```bash
OPENAI_API_KEY=sk-...
ENTRY_API_KEY=your-app-debug-token
ENTRY_HOST=0.0.0.0
ENTRY_PORT=8769
UVICORN_WORKERS=1
```

## Linux

```bash
chmod +x scripts/deploy_linux.sh
./scripts/deploy_linux.sh
```

Useful overrides:

```bash
ENTRY_PORT=8879 ./scripts/deploy_linux.sh
SKIP_INSTALL=1 ./scripts/deploy_linux.sh
```

## Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\deploy_windows.ps1
```

Useful overrides:

```powershell
$env:ENTRY_PORT = "8879"
.\scripts\deploy_windows.ps1 -SkipInstall
```

## App Debugging

Connect the App to:

```text
ws://<host>:<port>/api/ag-ui-ws?token=<ENTRY_API_KEY>
```

For HTTPS deployments, use:

```text
wss://<domain>/api/ag-ui-ws?token=<ENTRY_API_KEY>
```

After connecting, send the AG-UI payload as the first WebSocket text frame. Each response frame is one AG-UI event JSON object.

## Reverse Proxy Notes

If using Nginx, ALB, Cloudflare, or another gateway:

- Enable WebSocket upgrade for `/api/ag-ui-ws`.
- Use long read timeouts, at least 120 seconds for debugging.
- Prefer `Authorization: Bearer <ENTRY_API_KEY>` over query tokens outside local testing.
- Keep `UVICORN_WORKERS=1` until session state is moved out of process memory.
