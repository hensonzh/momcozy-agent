from __future__ import annotations

import os

from .config import load_project_env
from .server import create_app as create_web_app


def create_app():
    return create_web_app(include_websocket_bridge=True)


app = create_app()


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("uvicorn is not installed. Install the 'server' optional dependencies.") from exc

    load_project_env()
    host = os.getenv("ENTRY_HOST", "0.0.0.0")
    port = int(os.getenv("ENTRY_PORT", "8769"))
    uvicorn.run("momcozy_agent.api_app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
