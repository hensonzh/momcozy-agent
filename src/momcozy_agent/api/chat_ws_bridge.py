from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..agents import run_error_event


router = APIRouter()


DEFAULT_UPSTREAM_SSE_URL = "http://127.0.0.1:8768/api/ag-ui"
SSE_BOUNDARY_LF = "\n\n"
SSE_BOUNDARY_CRLF = "\r\n\r\n"


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
            await _bridge_sse_to_ws(websocket, payload)
        except WebSocketDisconnect:
            return
        except Exception as exc:
            await _send_run_error(websocket, f"upstream stream error: {exc}", type(exc).__name__)
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


async def _bridge_sse_to_ws(websocket: WebSocket, payload: dict[str, Any]) -> None:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError(
            "httpx is not installed; install the 'server' optional dependencies"
        ) from exc

    upstream_url = (os.getenv("MOMCOZY_CHAT_SSE_URL") or "").strip() or DEFAULT_UPSTREAM_SSE_URL
    timeout = httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream(
                "POST",
                upstream_url,
                json=payload,
                headers={
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status_code != 200:
                    body_preview = ""
                    try:
                        body_bytes = await resp.aread()
                        body_preview = body_bytes.decode("utf-8", errors="replace")[:300]
                    except Exception:
                        pass
                    await _send_run_error(
                        websocket,
                        f"upstream returned status {resp.status_code}: {body_preview}".strip(),
                        f"UPSTREAM_{resp.status_code}",
                    )
                    return

                buffer = ""
                async for chunk in resp.aiter_text():
                    if not chunk:
                        continue
                    buffer += chunk
                    while True:
                        boundary_idx, boundary_len = _find_boundary(buffer)
                        if boundary_idx == -1:
                            break
                        raw_event = buffer[:boundary_idx]
                        buffer = buffer[boundary_idx + boundary_len:]
                        await _emit_event(websocket, raw_event)

                if buffer.strip():
                    await _emit_event(websocket, buffer)
        except httpx.HTTPError as exc:
            await _send_run_error(
                websocket,
                f"upstream connection failed: {exc}",
                type(exc).__name__,
            )


def _find_boundary(buffer: str) -> tuple[int, int]:
    crlf_idx = buffer.find(SSE_BOUNDARY_CRLF)
    lf_idx = buffer.find(SSE_BOUNDARY_LF)
    if crlf_idx == -1 and lf_idx == -1:
        return -1, 0
    if crlf_idx == -1:
        return lf_idx, len(SSE_BOUNDARY_LF)
    if lf_idx == -1:
        return crlf_idx, len(SSE_BOUNDARY_CRLF)
    if crlf_idx <= lf_idx:
        return crlf_idx, len(SSE_BOUNDARY_CRLF)
    return lf_idx, len(SSE_BOUNDARY_LF)


async def _emit_event(websocket: WebSocket, raw_event: str) -> None:
    data_lines: list[str] = []
    for line in raw_event.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return
    data_str = "\n".join(data_lines)
    if not data_str:
        return
    try:
        obj = json.loads(data_str)
    except json.JSONDecodeError:
        return
    await websocket.send_text(json.dumps(obj, ensure_ascii=False))


async def _send_run_error(websocket: WebSocket, message: str, code: str | None = None) -> None:
    payload = run_error_event(message, code)
    try:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


async def _safe_close(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception:
        pass
