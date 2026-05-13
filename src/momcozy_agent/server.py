from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .agents import run_agent_loop, run_error_event
from .config import load_project_env
from .contexts import DEFAULT_LOCALE, DEFAULT_TIMEZONE, ContextState
from .types import SkillId

ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"
SKILLS_ROOT = ROOT / "skills"
HOST = "127.0.0.1"
PORT = 8768
MAX_IMAGE_ATTACHMENTS = 4
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/momcozy_logo.png": ("momcozy_logo.png", "image/png"),
    "/ibclc-chat.html": ("ibclc-chat.html", "text/html; charset=utf-8"),
}
STATIC_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".html": "text/html; charset=utf-8",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


@dataclass
class ChatSession:
    conversation_id: str
    previous_response_id: str | None = None
    loaded_skill_ids: list[SkillId] = field(default_factory=list)
    context_state: ContextState = field(default_factory=ContextState)


class ChatRuntime:
    def __init__(self, client: Any, *, model: str = "gpt-5.5", store: bool = True) -> None:
        self.client = client
        self.model = model
        self.store = store
        self.sessions: dict[str, ChatSession] = {}

    def get_session(self, conversation_id: str | None) -> ChatSession:
        if conversation_id and conversation_id in self.sessions:
            return self.sessions[conversation_id]

        new_id = conversation_id or str(uuid.uuid4())
        session = ChatSession(conversation_id=new_id)
        self.sessions[new_id] = session
        return session


def make_runtime() -> ChatRuntime:
    load_project_env(ROOT / ".env")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("The OpenAI SDK is not installed. Install it with: python3 -m pip install openai") from exc

    return ChatRuntime(OpenAI())


class ChatHandler(BaseHTTPRequestHandler):
    runtime: ChatRuntime

    def do_GET(self) -> None:
        self._handle_static_get(include_body=True)

    def do_HEAD(self) -> None:
        self._handle_static_get(include_body=False)

    def _handle_static_get(self, *, include_body: bool) -> None:
        path = urlparse(self.path).path
        static_file = STATIC_FILES.get(path)
        if static_file:
            filename, content_type = static_file
            self._send_file(WEB_ROOT / filename, content_type, include_body=include_body)
            return
        if path.startswith("/images/"):
            self._handle_static_asset(path, include_body=include_body)
            return
        if path.startswith("/skill-assets/"):
            self._handle_skill_asset(path, include_body=include_body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/ag-ui":
            self._handle_ag_ui_stream()
            return
        if path == "/api/support-ticket-submit":
            self._handle_support_ticket_submit()
            return
        if path == "/api/client-event":
            self._handle_client_event()
            return
        self.send_error(404)

    def _handle_client_event(self) -> None:
        try:
            payload = self._read_json()
            thread_id = str(_field(payload, "thread_id", "threadId") or payload.get("conversation_id") or "").strip()
            if not thread_id:
                raise ValueError("client event requires thread_id.")
            event = _format_client_event(payload)
            session = self.runtime.get_session(thread_id)
            if event not in session.context_state.client_events:
                session.context_state.client_events.append(event)
                session.context_state.client_events = session.context_state.client_events[-10:]
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json({
            "status": "recorded",
            "conversation_id": session.conversation_id,
            "consult_id": _client_event_consult_id(payload),
            "event": event,
            "session_state": _session_state_payload(session),
        })

    def _handle_support_ticket_submit(self) -> None:
        try:
            payload = self._read_json()
            ticket = payload.get("ticket")
            if not isinstance(ticket, dict):
                raise ValueError("support ticket submit requires a ticket object.")
            result = _submit_support_ticket(ticket)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json(result)

    def _handle_ag_ui_stream(self) -> None:
        try:
            payload = self._read_json()
            inputs = _runtime_inputs_from_ag_ui(payload)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        thread_id = _field(payload, "thread_id", "threadId") or f"thread_{payload.get('conversation_id', 'anonymous')}"
        run_id = _field(payload, "run_id", "runId") or f"run_{date.today().isoformat()}"
        parent_run_id = _field(payload, "parent_run_id", "parentRunId")
        assistant_message_id = f"{run_id}:assistant"
        session = self.runtime.get_session(str(thread_id))
        if session.previous_response_id and "previous_response_id" not in inputs:
            inputs["previous_response_id"] = session.previous_response_id

        pending_run_finished: dict[str, Any] | None = None
        pending_assistant_followups: list[str] = []
        text_started = False
        streamed_text_parts: list[str] = []

        def send_ag_ui_event(event: dict[str, Any]) -> None:
            nonlocal pending_run_finished
            if event.get("type") == "RUN_FINISHED":
                pending_run_finished = event
                return
            followup = _assistant_followup_from_tool_result_event(event)
            if followup and followup not in pending_assistant_followups:
                pending_assistant_followups.append(followup)
            self._send_sse_event(event)

        def send_text_delta(delta: str) -> None:
            nonlocal text_started
            if not text_started:
                self._send_sse_event({"type": "TEXT_MESSAGE_START", "message_id": assistant_message_id, "role": "assistant"})
                text_started = True
            streamed_text_parts.append(delta)
            self._send_sse_event({"type": "TEXT_MESSAGE_CONTENT", "message_id": assistant_message_id, "delta": delta})

        try:
            agent_options: dict[str, Any] = {
                "model": self.runtime.model,
                "store": self.runtime.store,
                "loaded_skill_ids": session.loaded_skill_ids,
                "context_state": session.context_state,
            }
            response = run_agent_loop(
                self.runtime.client,
                inputs,
                agent_options,
                on_ag_ui_event=send_ag_ui_event,
                ag_ui_thread_id=str(thread_id),
                ag_ui_run_id=str(run_id),
                ag_ui_parent_run_id=str(parent_run_id) if parent_run_id else None,
                on_text_delta=send_text_delta,
            )
            response_id = _response_id(response)
            if response_id:
                session.previous_response_id = response_id
            loaded_skill_ids = agent_options.get("loaded_skill_ids")
            if isinstance(loaded_skill_ids, list):
                session.loaded_skill_ids = loaded_skill_ids
            text = _response_text(response)
            if not streamed_text_parts and text:
                send_text_delta(text)
            current_text = "".join(streamed_text_parts) or text
            for followup in pending_assistant_followups:
                if _should_send_assistant_followup(followup, current_text):
                    send_text_delta(f"\n\n{followup}")
                    current_text = f"{current_text}\n\n{followup}"
            if text_started:
                self._send_sse_event({"type": "TEXT_MESSAGE_END", "message_id": assistant_message_id})
            if pending_run_finished:
                self._send_sse_event(pending_run_finished)
        except Exception as exc:
            self._send_sse_event(run_error_event(str(exc), type(exc).__name__))

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse_event(self, payload: dict[str, Any]) -> None:
        body = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
        self.wfile.write(body)
        self.wfile.flush()

    def _send_file(self, path: Path, content_type: str, *, include_body: bool = True) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _handle_static_asset(self, request_path: str, *, include_body: bool) -> None:
        asset_path = (WEB_ROOT / request_path.lstrip("/")).resolve()
        web_root = WEB_ROOT.resolve()
        if web_root not in asset_path.parents or not asset_path.is_file():
            self.send_error(404)
            return
        content_type = STATIC_CONTENT_TYPES.get(asset_path.suffix.lower())
        if content_type is None:
            self.send_error(404)
            return
        self._send_file(asset_path, content_type, include_body=include_body)

    def _handle_skill_asset(self, request_path: str, *, include_body: bool) -> None:
        relative_path = request_path.removeprefix("/skill-assets/")
        skill_id, _, asset_name = relative_path.partition("/")
        if not skill_id or not asset_name:
            self.send_error(404)
            return
        asset_path = (SKILLS_ROOT / skill_id / "assets" / asset_name).resolve()
        skill_assets_root = (SKILLS_ROOT / skill_id / "assets").resolve()
        if skill_assets_root not in asset_path.parents or not asset_path.is_file():
            self.send_error(404)
            return
        content_type = STATIC_CONTENT_TYPES.get(asset_path.suffix.lower())
        if content_type is None:
            self.send_error(404)
            return
        self._send_file(asset_path, content_type, include_body=include_body)


def main() -> None:
    ChatHandler.runtime = make_runtime()
    server = ThreadingHTTPServer((HOST, PORT), ChatHandler)
    print(f"Momcozy agent test UI: http://{HOST}:{PORT}")
    server.serve_forever()


def _runtime_inputs_from_ag_ui(payload: dict[str, Any]) -> dict[str, Any]:
    message = _latest_user_message(payload.get("messages", []))
    images = _latest_user_images(payload.get("messages", []))
    if not message:
        message = str(payload.get("message", "")).strip()
    if not message and images:
        message = "请根据我发送的图片提供帮助。"
    if not message:
        raise ValueError("AG-UI input requires a user message.")

    state = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    forwarded_props = _field(payload, "forwarded_props", "forwardedProps")
    if not isinstance(forwarded_props, dict):
        forwarded_props = {}

    timezone = forwarded_props.get("timezone") or state.get("timezone") or payload.get("timezone") or DEFAULT_TIMEZONE
    message_sent_at = (
        forwarded_props.get("message_sent_at")
        or state.get("message_sent_at")
        or payload.get("message_sent_at")
        or _now_in_timezone(str(timezone)).isoformat(timespec="seconds")
    )

    inputs: dict[str, Any] = {
        "user_message": message,
        "locale": forwarded_props.get("locale") or state.get("locale") or payload.get("locale", DEFAULT_LOCALE),
        "timezone": timezone,
        "message_sent_at": message_sent_at,
    }
    if images:
        inputs["images"] = images

    for key in ("user_profile", "baby_profile", "service_state", "retrieved_records", "retrieved_knowledge"):
        if key in state:
            inputs[key] = state[key]
        elif key in forwarded_props:
            inputs[key] = forwarded_props[key]

    previous_response_id = forwarded_props.get("previous_response_id") or state.get("previous_response_id")
    if previous_response_id:
        inputs["previous_response_id"] = previous_response_id

    return inputs


def _assistant_followup_from_tool_result_event(event: dict[str, Any]) -> str | None:
    if event.get("type") != "TOOL_CALL_RESULT":
        return None
    content = event.get("content")
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    followup = payload.get("assistant_followup")
    if not isinstance(followup, dict):
        return None
    message = followup.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return None


def _submit_support_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    ticket_id = f"mock_ticket_{uuid.uuid4().hex[:8]}"
    return {
        "status": "mock_submitted",
        "ticket_id": ticket_id,
        "side_effect_performed": False,
        "mock": True,
        "message": "工单已提交，人工客服会在 24 小时内联系你解决问题。",
        "ticket": ticket,
    }


def _format_client_event(payload: dict[str, Any]) -> str:
    event_type = str(payload.get("event_type") or payload.get("type") or "client_event").strip()
    label = str(payload.get("label") or event_type).strip()
    occurred_at = str(payload.get("occurred_at") or payload.get("message_sent_at") or "").strip()
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    detail_parts = []
    for key in ("consultant_name", "consultant_credentials", "source", "consult_id"):
        value = metadata.get(key)
        if value:
            detail_parts.append(f"{key}: {value}")
    details = f" ({'; '.join(detail_parts)})" if detail_parts else ""
    time_prefix = f"{occurred_at}: " if occurred_at else ""
    return f"{time_prefix}{label} [event_type: {event_type}]{details}"


def _client_event_consult_id(payload: dict[str, Any]) -> str:
    value = payload.get("consult_id") or payload.get("consultId")
    if not value and isinstance(payload.get("metadata"), dict):
        value = payload["metadata"].get("consult_id") or payload["metadata"].get("consultId")
    return str(value or "").strip()


def _session_state_payload(session: ChatSession) -> dict[str, Any]:
    return {
        "conversation_id": session.conversation_id,
        "previous_response_id": session.previous_response_id,
        "loaded_skill_ids": list(session.loaded_skill_ids),
        "context_state": {
            "environment_sent": session.context_state.environment_sent,
            "loaded_references": list(session.context_state.loaded_references),
            "client_events": list(session.context_state.client_events),
        },
    }


def _should_send_assistant_followup(followup: str, current_text: str) -> bool:
    if not followup.strip():
        return False
    if followup in current_text:
        return False
    if "sea.momcozy.com" in followup and "sea.momcozy.com" in current_text:
        return False
    return True


def _latest_user_message(messages: Any) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts).strip()
    return ""


def _latest_user_images(messages: Any) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            return []
        images: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict) or item.get("type") not in {"image", "input_image"}:
                continue
            image_url = item.get("image_url") or item.get("url") or item.get("data_url")
            if not isinstance(image_url, str) or not _is_supported_image_url(image_url):
                continue
            image: dict[str, Any] = {"image_url": image_url, "detail": _image_detail(item.get("detail"))}
            for key in ("mime_type", "name", "size"):
                if key in item:
                    image[key] = item[key]
            images.append(image)
            if len(images) >= MAX_IMAGE_ATTACHMENTS:
                break
        return images
    return []


def _is_supported_image_url(value: str) -> bool:
    return value.startswith("data:image/") or value.startswith("https://") or value.startswith("http://")


def _image_detail(value: Any) -> str:
    return str(value) if value in {"low", "high", "auto"} else "auto"


def _now_in_timezone(timezone: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        return datetime.now(ZoneInfo(DEFAULT_TIMEZONE))


def _field(payload: dict[str, Any], snake_case: str, camel_case: str) -> Any:
    if snake_case in payload:
        return payload[snake_case]
    return payload.get(camel_case)


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    parts: list[str] = []
    for item in _output_items(response):
        if _get(item, "type") != "message":
            continue
        for content in _get(item, "content", []):
            if _get(content, "type") == "output_text":
                text = _get(content, "text")
                if text:
                    parts.append(text)
    return "\n".join(parts).strip()


def _response_id(response: Any) -> str | None:
    if isinstance(response, dict):
        response_id = response.get("id")
    else:
        response_id = getattr(response, "id", None)
    return response_id if isinstance(response_id, str) else None


def _output_items(response: Any) -> list[Any]:
    if isinstance(response, dict):
        return response.get("output", [])
    return getattr(response, "output", []) or []


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)
