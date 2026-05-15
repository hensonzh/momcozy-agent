from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CHAT_HOST = "127.0.0.1"
CHAT_PORT = 8768


def main() -> None:
    sys.path.insert(0, str(SRC))

    from momcozy_agent.config import load_project_env
    from momcozy_agent.server import main as run_chat_server

    load_project_env(ROOT / ".env")
    CHAT_HOST = os.getenv("CHAT_HOST", "127.0.0.1")
    CHAT_PORT = int(os.getenv("CHAT_PORT", "8768"))
    os.environ.setdefault("MOMCOZY_CHAT_SSE_URL", f"http://{CHAT_HOST}:{CHAT_PORT}/api/ag-ui")

    host = os.getenv("ENTRY_HOST", "0.0.0.0")
    port = int(os.getenv("ENTRY_PORT", "8769"))
    if _is_port_open(_connect_host(host), port):
        raise RuntimeError(
            f"Unified API port {host}:{port} is already in use. "
            "Stop the existing service, or set ENTRY_PORT to another port in .env."
        )

    if not (os.getenv("ENTRY_API_KEY") or "").strip():
        print("Warning: ENTRY_API_KEY is not set; /api/ag-ui-ws will reject WebSocket clients.")

    if not _is_port_open(CHAT_HOST, CHAT_PORT):
        chat_thread = threading.Thread(target=run_chat_server, name="momcozy-chat-sse", daemon=True)
        chat_thread.start()
        _wait_for_port(CHAT_HOST, CHAT_PORT, timeout_seconds=30)

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is not installed. Install dependencies with: py -3.12 -m pip install -r requirements.txt") from exc

    print(f"Momcozy unified API: http://{host}:{port}")
    print(f"Momcozy App WebSocket: ws://{host}:{port}/api/ag-ui-ws")
    print(f"Momcozy chat SSE upstream: http://{CHAT_HOST}:{CHAT_PORT}/api/ag-ui")
    uvicorn.run("momcozy_agent.api_app:app", host=host, port=port, reload=False)


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _connect_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


def _wait_for_port(host: str, port: int, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _is_port_open(host, port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for chat SSE server on {host}:{port}")


if __name__ == "__main__":
    main()
