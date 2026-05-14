from __future__ import annotations

import json
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..agents import run_error_event
from ..server import _runtime_inputs_from_ag_ui, runtime_from_app, stream_ag_ui_events

router = APIRouter()


@router.websocket("/api/ag-ui-ws")
async def chat_ws_bridge(websocket: WebSocket) -> None:
    if not _verify_token(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        try:
            raw_first = await websocket.receive_text()
        except WebSocketDisconnect:
            return

        try:
            payload = json.loads(raw_first or "{}")
        except json.JSONDecodeError:
            await _send_run_error(websocket, "first frame must be valid JSON", "INVALID_REQUEST")
            return
        if not isinstance(payload, dict):
            await _send_run_error(websocket, "first frame must be a JSON object", "INVALID_REQUEST")
            return

        try:
            inputs = _runtime_inputs_from_ag_ui(payload)
        except ValueError as exc:
            await _send_run_error(websocket, str(exc), "INVALID_REQUEST")
            return

        try:
            runtime = runtime_from_app(websocket.app)
            async for event in stream_ag_ui_events(payload, inputs, runtime):
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
        except WebSocketDisconnect:
            return
        except Exception as exc:
            await _send_run_error(websocket, str(exc), type(exc).__name__)
    finally:
        await _safe_close(websocket)


def _verify_token(websocket: WebSocket) -> bool:
    expected = (os.getenv("ENTRY_API_KEY") or "").strip()
    if not expected:
        return False

    query_token = (websocket.query_params.get("token") or "").strip()
    if query_token and query_token == expected:
        return True

    auth_header = websocket.headers.get("authorization") or ""
    if auth_header.startswith("Bearer "):
        header_token = auth_header[7:].strip()
        if header_token and header_token == expected:
            return True

    protocol_header = websocket.headers.get("sec-websocket-protocol") or ""
    for fragment in protocol_header.split(","):
        token = fragment.strip()
        if token and token == expected:
            return True

    return False


async def _send_run_error(websocket: WebSocket, message: str, code: str | None = None) -> None:
    payload = run_error_event(message, code)
    if code:
        payload["code"] = code
    try:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


async def _safe_close(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception:
        pass
