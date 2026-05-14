from __future__ import annotations

import os

from .config import load_project_env
from .services.paths import ensure_runtime_dirs


def create_app():
    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError("FastAPI is not installed. Install the 'server' optional dependencies.") from exc

    from .api.chat_ws_bridge import router as chat_ws_router
    from .api.routes import router
    from .api.vision_stream import router as vision_router

    load_project_env()
    ensure_runtime_dirs()
    app = FastAPI(title="Momcozy Agent API")
    app.include_router(router)
    app.include_router(vision_router)
    app.include_router(chat_ws_router)
    return app


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
