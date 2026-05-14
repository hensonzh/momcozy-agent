from __future__ import annotations

import os
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def main() -> None:
    sys.path.insert(0, str(SRC))

    from momcozy_agent.config import load_project_env

    load_project_env(ROOT / ".env")

    host = os.getenv("ENTRY_HOST", "0.0.0.0")
    port = int(os.getenv("ENTRY_PORT", "8769"))
    if _is_port_open(_connect_host(host), port):
        raise RuntimeError(
            f"Momcozy API port {host}:{port} is already in use. "
            "Stop the existing service, or set ENTRY_PORT to another port in .env."
        )

    if not (os.getenv("ENTRY_API_KEY") or "").strip():
        print("Warning: ENTRY_API_KEY is not set; /api/ag-ui-ws will reject WebSocket clients.")

    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is not installed. Install the 'server' optional dependencies.") from exc

    print(f"Momcozy API: http://{host}:{port}")
    print(f"Momcozy Web Demo: http://{host}:{port}/")
    print(f"Momcozy App WebSocket: ws://{host}:{port}/api/ag-ui-ws")
    uvicorn.run("momcozy_agent.api_app:app", host=host, port=port, reload=False)


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _connect_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


if __name__ == "__main__":
    main()
