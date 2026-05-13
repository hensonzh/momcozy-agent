from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from .contexts import ContextState, build_request_context
from .static_context import STATIC_AGENT_INSTRUCTIONS
from .tool_registry import execute_tool, select_runtime_tools
from .types import AgUiEvent, AgUiEventHandler, AgentEvent, AgentEventHandler, AgentEventPhase, BuildAgentRequestOptions, ResponsesClientLike, ResponsesRequest, RuntimeInputs, TextDeltaHandler

AG_UI_STATUS_ACTIVITY_TYPE = "MOMCOZY_AGENT_STATUS"
AG_UI_STATUS_CUSTOM_NAME = "momcozy.agent.status"
AG_UI_THINKING_CUSTOM_NAME = "momcozy.agent.thinking"

MAX_TOOL_ROUNDS = 6


def new_ag_ui_run_id() -> str:
    return f"run_{uuid4().hex}"


def default_ag_ui_thread_id(inputs: RuntimeInputs) -> str:
    user_id = inputs.get("user_profile", {}).get("user_id")
    if isinstance(user_id, str) and user_id:
        return f"thread_{user_id}"
    return "thread_anonymous"


def run_started_event(thread_id: str, run_id: str, parent_run_id: str | None = None, input_payload: Any | None = None) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "RUN_STARTED",
        "timestamp": _timestamp_ms(),
        "thread_id": thread_id,
        "run_id": run_id,
    }
    if parent_run_id:
        event["parent_run_id"] = parent_run_id
    if input_payload is not None:
        event["input"] = input_payload
    return event


def run_finished_event(thread_id: str, run_id: str, result: Any | None = None) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "RUN_FINISHED",
        "timestamp": _timestamp_ms(),
        "thread_id": thread_id,
        "run_id": run_id,
    }
    if result is not None:
        event["result"] = result
    return event


def run_error_event(message: str, code: str | None = None) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "RUN_ERROR",
        "timestamp": _timestamp_ms(),
        "message": message,
    }
    if code:
        event["code"] = code
    return event


def step_started_event(step_name: str) -> AgUiEvent:
    return {
        "type": "STEP_STARTED",
        "timestamp": _timestamp_ms(),
        "step_name": step_name,
    }


def step_finished_event(step_name: str) -> AgUiEvent:
    return {
        "type": "STEP_FINISHED",
        "timestamp": _timestamp_ms(),
        "step_name": step_name,
    }


def tool_call_start_event(
    tool_call_id: str,
    tool_call_name: str,
    parent_message_id: str | None = None,
    *,
    response_id: str | None = None,
    output_index: int | None = None,
    item_id: str | None = None,
) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "TOOL_CALL_START",
        "timestamp": _timestamp_ms(),
        "tool_call_id": tool_call_id,
        "tool_call_name": tool_call_name,
    }
    if parent_message_id:
        event["parent_message_id"] = parent_message_id
    if response_id:
        event["response_id"] = response_id
    if output_index is not None:
        event["output_index"] = output_index
    if item_id:
        event["item_id"] = item_id
    return event


def tool_call_args_event(
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    response_id: str | None = None,
    output_index: int | None = None,
    item_id: str | None = None,
) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "TOOL_CALL_ARGS",
        "timestamp": _timestamp_ms(),
        "tool_call_id": tool_call_id,
        "delta": json.dumps(safe_tool_arguments(tool_name, arguments), ensure_ascii=False),
    }
    if response_id:
        event["response_id"] = response_id
    if output_index is not None:
        event["output_index"] = output_index
    if item_id:
        event["item_id"] = item_id
    return event


def tool_call_end_event(
    tool_call_id: str,
    *,
    response_id: str | None = None,
    output_index: int | None = None,
    item_id: str | None = None,
) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "TOOL_CALL_END",
        "timestamp": _timestamp_ms(),
        "tool_call_id": tool_call_id,
    }
    if response_id:
        event["response_id"] = response_id
    if output_index is not None:
        event["output_index"] = output_index
    if item_id:
        event["item_id"] = item_id
    return event


def tool_call_result_event(
    message_id: str,
    tool_call_id: str,
    result: dict[str, Any],
    *,
    response_id: str | None = None,
    output_index: int | None = None,
    item_id: str | None = None,
) -> AgUiEvent:
    event: AgUiEvent = {
        "type": "TOOL_CALL_RESULT",
        "timestamp": _timestamp_ms(),
        "message_id": message_id,
        "tool_call_id": tool_call_id,
        "content": json.dumps(safe_tool_result(result), ensure_ascii=False),
        "role": "tool",
    }
    if response_id:
        event["response_id"] = response_id
    if output_index is not None:
        event["output_index"] = output_index
    if item_id:
        event["item_id"] = item_id
    return event


def status_activity_snapshot_event(message_id: str, event: AgentEvent) -> AgUiEvent:
    return {
        "type": "ACTIVITY_SNAPSHOT",
        "timestamp": _timestamp_ms(),
        "message_id": message_id,
        "activity_type": AG_UI_STATUS_ACTIVITY_TYPE,
        "content": event,
        "replace": True,
    }


def status_custom_event(event: AgentEvent) -> AgUiEvent:
    return {
        "type": "CUSTOM",
        "timestamp": _timestamp_ms(),
        "name": AG_UI_STATUS_CUSTOM_NAME,
        "value": event,
    }


def thinking_custom_event(status: str, metadata: dict[str, Any] | None = None) -> AgUiEvent:
    return {
        "type": "CUSTOM",
        "timestamp": _timestamp_ms(),
        "name": AG_UI_THINKING_CUSTOM_NAME,
        "value": {
            "type": "agent.thinking",
            "status": status,
            "metadata": metadata or {},
        },
    }


def safe_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name in {"load_skill", "read_skill_file", "search_skill_assets", "run_approved_skill_script"}:
        return {key: arguments[key] for key in ("skill_id", "kind", "path", "script_name", "query") if key in arguments}

    redacted: dict[str, Any] = {"argument_keys": sorted(arguments.keys())}
    if "idempotency_key" in arguments:
        redacted["has_idempotency_key"] = True
    return redacted


def safe_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "tool_name": result.get("tool_name"),
    }
    tool_result = result.get("result")
    if isinstance(tool_result, dict):
        for key in ("id", "skill_id", "status", "resource_id", "side_effect_performed"):
            if key in tool_result:
                safe[key] = tool_result[key]
        if result.get("tool_name") == "ui_form_create" and isinstance(tool_result.get("form"), dict):
            safe["form"] = tool_result["form"]
        if result.get("tool_name") == "ui_card_create" and isinstance(tool_result.get("card"), dict):
            safe["card"] = tool_result["card"]
            if isinstance(tool_result.get("assistant_followup"), dict):
                safe["assistant_followup"] = tool_result["assistant_followup"]
        if result.get("tool_name") == "ibclc_consult_card_create" and isinstance(tool_result.get("card"), dict):
            safe["card"] = tool_result["card"]
        if result.get("tool_name") == "support_ticket_draft_create" and isinstance(tool_result.get("ticket"), dict):
            safe["ticket"] = tool_result["ticket"]
            if "submit_label" in tool_result:
                safe["submit_label"] = tool_result["submit_label"]
    if isinstance(result.get("error"), dict):
        safe["error"] = result["error"]
    return safe


def _timestamp_ms() -> int:
    return int(time.time() * 1000)


def build_agent_request(inputs: RuntimeInputs, options: BuildAgentRequestOptions | None = None) -> ResponsesRequest:
    options = options or {}
    request_context = _build_request_context_for_request(inputs, options)
    return _build_response_request(inputs, options, [_user_input_item(request_context, inputs["user_message"], inputs.get("images", []))])


def _build_response_request(
    inputs: RuntimeInputs,
    options: BuildAgentRequestOptions,
    input_items: list[dict[str, Any]],
) -> ResponsesRequest:
    tools = select_runtime_tools()

    request: ResponsesRequest = {
        "model": options.get("model", "gpt-5.5"),
        "instructions": STATIC_AGENT_INSTRUCTIONS,
        "input": input_items,
        "tools": tools,
        "tool_choice": "auto",
        "reasoning": {"effort": "medium"},
        "text": {
            "format": {"type": "text"},
            "verbosity": "medium",
        },
        "store": options.get("store", True),
        "prompt_cache_key": options.get("prompt_cache_key", "momcozy-agent-v2"),
    }

    previous_response_id = inputs.get("previous_response_id")
    if previous_response_id:
        request["previous_response_id"] = previous_response_id

    return request


def run_agent_turn(
    client: ResponsesClientLike,
    inputs: RuntimeInputs,
    options: BuildAgentRequestOptions | None = None,
) -> object:
    request = build_agent_request(inputs, options)
    return client.responses.create(**request)


def run_agent_loop(
    client: ResponsesClientLike,
    inputs: RuntimeInputs,
    options: BuildAgentRequestOptions | None = None,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    on_event: AgentEventHandler | None = None,
    on_ag_ui_event: AgUiEventHandler | None = None,
    ag_ui_thread_id: str | None = None,
    ag_ui_run_id: str | None = None,
    ag_ui_parent_run_id: str | None = None,
    on_text_delta: TextDeltaHandler | None = None,
) -> object:
    options = dict(options or {})
    loaded_skill_ids = list(options.get("loaded_skill_ids", []))
    ag_ui_thread_id = ag_ui_thread_id or default_ag_ui_thread_id(inputs)
    ag_ui_run_id = ag_ui_run_id or new_ag_ui_run_id()
    ag_ui_status_message_id = f"{ag_ui_run_id}:status"
    ag_ui_tool_result_message_id = f"{ag_ui_run_id}:tool-results"
    streamed_tool_call_keys: set[str] = set()

    def emit_streamed_tool_start(tool_call: dict[str, Any]) -> None:
        if _tool_call_was_seen(streamed_tool_call_keys, tool_call):
            return
        _remember_tool_call(streamed_tool_call_keys, tool_call)
        _emit_ag_ui_event(
            on_ag_ui_event,
            tool_call_start_event(
                tool_call["call_id"],
                tool_call["name"],
                ag_ui_tool_result_message_id,
                response_id=tool_call.get("response_id"),
                output_index=tool_call.get("output_index"),
                item_id=tool_call.get("item_id"),
            ),
        )

    _emit_ag_ui_event(on_ag_ui_event, run_started_event(ag_ui_thread_id, ag_ui_run_id, ag_ui_parent_run_id))
    _emit_event(on_event, "started", "Agent loop started.", {"max_tool_rounds": max_tool_rounds}, on_ag_ui_event, ag_ui_status_message_id)
    _emit_event(on_event, "requesting_model", "Requesting model response.", {"round": 0}, on_ag_ui_event, ag_ui_status_message_id)
    try:
        request = build_agent_request(inputs, options)
        response = _create_response(
            client,
            request,
            on_text_delta,
            lambda status, metadata: _emit_thinking(on_ag_ui_event, status, metadata),
            emit_streamed_tool_start,
        )
    except Exception as exc:
        _emit_event(on_event, "failed", "Model request failed.", _error_metadata(exc), on_ag_ui_event, ag_ui_status_message_id)
        _emit_ag_ui_event(on_ag_ui_event, run_error_event(str(exc), type(exc).__name__))
        raise

    for round_index in range(max_tool_rounds):
        tool_calls = _extract_function_calls(response)
        if not tool_calls:
            _emit_event(
                on_event,
                "completed",
                "Agent loop completed.",
                {"round": round_index, "response_id": _get_response_id(response)},
                on_ag_ui_event,
                ag_ui_status_message_id,
            )
            _emit_ag_ui_event(on_ag_ui_event, run_finished_event(ag_ui_thread_id, ag_ui_run_id, {"response_id": _get_response_id(response)}))
            return response

        tool_outputs = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            if not _tool_call_was_seen(streamed_tool_call_keys, tool_call):
                _remember_tool_call(streamed_tool_call_keys, tool_call)
                _emit_ag_ui_event(
                    on_ag_ui_event,
                    tool_call_start_event(
                        tool_call["call_id"],
                        tool_name,
                        ag_ui_tool_result_message_id,
                        response_id=tool_call.get("response_id"),
                        output_index=tool_call.get("output_index"),
                        item_id=tool_call.get("item_id"),
                    ),
                )
            _emit_ag_ui_event(
                on_ag_ui_event,
                tool_call_args_event(
                    tool_call["call_id"],
                    tool_name,
                    tool_call["arguments"],
                    response_id=tool_call.get("response_id"),
                    output_index=tool_call.get("output_index"),
                    item_id=tool_call.get("item_id"),
                ),
            )
            _emit_ag_ui_event(
                on_ag_ui_event,
                tool_call_end_event(
                    tool_call["call_id"],
                    response_id=tool_call.get("response_id"),
                    output_index=tool_call.get("output_index"),
                    item_id=tool_call.get("item_id"),
                ),
            )
            _emit_event(
                on_event,
                "model_tool_call",
                _tool_call_message(tool_name),
                {"round": round_index, "tool_name": tool_name},
                on_ag_ui_event,
                ag_ui_status_message_id,
            )
            _emit_event(
                on_event,
                _tool_execution_phase(tool_name),
                _tool_execution_message(tool_name),
                {"round": round_index, "tool_name": tool_name},
                on_ag_ui_event,
                ag_ui_status_message_id,
            )
            result = _execute_project_tool(tool_call["name"], tool_call["arguments"], _tool_inputs_for_call(inputs, options))
            if tool_call["name"] == "load_skill" and result.get("ok") and result.get("result", {}).get("id"):
                skill_id = result["result"]["id"]
                if skill_id not in loaded_skill_ids:
                    loaded_skill_ids.append(skill_id)
            _record_loaded_reference(options.get("context_state"), tool_call["name"], result)
            _emit_ag_ui_event(
                on_ag_ui_event,
                tool_call_result_event(
                    ag_ui_tool_result_message_id,
                    tool_call["call_id"],
                    result,
                    response_id=tool_call.get("response_id"),
                    output_index=tool_call.get("output_index"),
                    item_id=tool_call.get("item_id"),
                ),
            )
            _emit_event(
                on_event,
                "tool_completed",
                _tool_completed_message(tool_name, bool(result.get("ok"))),
                _tool_result_metadata(round_index, tool_name, result),
                on_ag_ui_event,
                ag_ui_status_message_id,
            )
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call["call_id"],
                    "output": json.dumps(result, ensure_ascii=False),
                }
            )

        options["loaded_skill_ids"] = loaded_skill_ids
        next_inputs = dict(inputs)
        response_id = _get_response_id(response)
        if response_id:
            next_inputs["previous_response_id"] = response_id

        request = _build_response_request(next_inputs, options, tool_outputs)
        _emit_event(
            on_event,
            "requesting_model",
            "Requesting model response with tool outputs.",
            {"round": round_index + 1},
            on_ag_ui_event,
            ag_ui_status_message_id,
        )
        try:
            response = _create_response(
                client,
                request,
                on_text_delta,
                lambda status, metadata: _emit_thinking(on_ag_ui_event, status, metadata),
                emit_streamed_tool_start,
            )
        except Exception as exc:
            _emit_event(on_event, "failed", "Model request failed.", _error_metadata(exc, {"round": round_index + 1}), on_ag_ui_event, ag_ui_status_message_id)
            _emit_ag_ui_event(on_ag_ui_event, run_error_event(str(exc), type(exc).__name__))
            raise

    _emit_event(
        on_event,
        "failed",
        "Agent loop reached the maximum tool rounds.",
        {"max_tool_rounds": max_tool_rounds},
        on_ag_ui_event,
        ag_ui_status_message_id,
    )
    _emit_ag_ui_event(on_ag_ui_event, run_error_event("Agent loop reached the maximum tool rounds.", "MAX_TOOL_ROUNDS"))
    return response


def _create_response(
    client: ResponsesClientLike,
    request: ResponsesRequest,
    on_text_delta: TextDeltaHandler | None = None,
    on_reasoning_event: Any | None = None,
    on_function_call_start: Any | None = None,
) -> object:
    if on_text_delta is None:
        return client.responses.create(**request)

    final_response = None
    reasoning_active = False
    stream = client.responses.create(**request, stream=True)
    for event in stream:
        event_type = _get_item_value(event, "type")
        if _is_reasoning_start_event(event_type, event):
            if not reasoning_active:
                reasoning_active = True
                if on_reasoning_event is not None:
                    on_reasoning_event("started", {"source_event": event_type})
        if event_type == "response.output_text.delta":
            delta = _get_item_value(event, "delta")
            if isinstance(delta, str) and delta:
                on_text_delta(delta)
        elif event_type == "response.output_item.added":
            item = _get_item_value(event, "item")
            if _is_function_call_item(item) and on_function_call_start is not None:
                on_function_call_start(_stream_function_call_from_event(event, item))
        elif event_type == "response.function_call_arguments.done":
            item = _get_item_value(event, "item")
            if _is_function_call_item(item) and on_function_call_start is not None:
                on_function_call_start(_stream_function_call_from_event(event, item))
        elif _is_message_done_event(event_type, event):
            if on_reasoning_event is not None:
                on_reasoning_event("running", {"source_event": event_type, "after_output_text": True})
        elif _is_reasoning_done_event(event_type, event):
            if reasoning_active and on_reasoning_event is not None:
                on_reasoning_event("completed", {"source_event": event_type})
            reasoning_active = False
        elif event_type == "response.completed":
            if reasoning_active and on_reasoning_event is not None:
                on_reasoning_event("completed", {"source_event": event_type})
            reasoning_active = False
            final_response = _get_item_value(event, "response")
        elif event_type == "response.failed":
            if reasoning_active and on_reasoning_event is not None:
                on_reasoning_event("failed", {"source_event": event_type})
            reasoning_active = False
            response = _get_item_value(event, "response")
            error = _get_item_value(response, "error") if response is not None else None
            message = _get_item_value(error, "message") or "Response stream failed."
            raise RuntimeError(message)

    if final_response is None:
        raise RuntimeError("Response stream ended without a completed response.")
    return final_response


def _emit_thinking(on_ag_ui_event: AgUiEventHandler | None, status: str, metadata: dict[str, Any] | None = None) -> None:
    _emit_ag_ui_event(on_ag_ui_event, thinking_custom_event(status, metadata))


def _is_reasoning_start_event(event_type: Any, event: object) -> bool:
    if not isinstance(event_type, str):
        return False
    if event_type.startswith("response.reasoning") and not event_type.endswith(".done"):
        return True
    if event_type == "response.output_item.added":
        item = _get_item_value(event, "item")
        return _get_item_value(item, "type") == "reasoning"
    return False


def _is_reasoning_done_event(event_type: Any, event: object) -> bool:
    if not isinstance(event_type, str):
        return False
    if event_type.startswith("response.reasoning") and event_type.endswith(".done"):
        return True
    if event_type == "response.output_item.done":
        item = _get_item_value(event, "item")
        return _get_item_value(item, "type") == "reasoning"
    return False


def _is_message_done_event(event_type: Any, event: object) -> bool:
    if event_type != "response.output_item.done":
        return False
    item = _get_item_value(event, "item")
    return _get_item_value(item, "type") == "message"


def _user_input_item(request_context: str, user_message: str, images: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    content = [
        {"type": "input_text", "text": request_context},
        {"type": "input_text", "text": f"user_message:\n{user_message}"},
    ]
    for image in images or []:
        image_url = image.get("image_url")
        if not isinstance(image_url, str) or not image_url:
            continue
        content.append(
            {
                "type": "input_image",
                "image_url": image_url,
                "detail": _image_detail(image.get("detail")),
            }
        )
    return {
        "role": "user",
        "content": content,
    }


def _image_detail(value: object) -> str:
    if value in {"low", "high", "auto"}:
        return str(value)
    return "auto"


def _build_request_context_for_request(
    inputs: RuntimeInputs,
    options: BuildAgentRequestOptions,
) -> str:
    context_state = options.get("context_state")
    if isinstance(context_state, ContextState):
        return build_request_context(inputs, context_state)
    return build_request_context(inputs)


def _record_loaded_reference(context_state: object, tool_name: str, result: dict[str, Any]) -> None:
    if not isinstance(context_state, ContextState):
        return
    if tool_name != "device_manual_search" or not result.get("ok"):
        return
    tool_result = result.get("result")
    if not isinstance(tool_result, dict):
        return
    if tool_result.get("status") not in {"manual_loaded", "manual_loaded_with_faq"}:
        return
    model = str(tool_result.get("model") or "").strip()
    manual = tool_result.get("manual")
    if model != "Air1" or not isinstance(manual, dict):
        return
    source = str(manual.get("source") or "references/air1/manual.md")
    reference = f"device-guidance/{model}/{source} 已在当前会话中加载过；后续同型号连续任务可复用，除非上下文不足或用户提出新的资料需求。"
    if reference not in context_state.loaded_references:
        context_state.loaded_references.append(reference)


def _tool_inputs_for_call(inputs: RuntimeInputs, options: BuildAgentRequestOptions) -> RuntimeInputs:
    tool_inputs = dict(inputs)
    context_state = options.get("context_state")
    if isinstance(context_state, ContextState):
        tool_inputs["_loaded_references"] = list(context_state.loaded_references)
    return tool_inputs


def _execute_project_tool(name: str, arguments: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    try:
        result = execute_tool(name, arguments, inputs)
        return {"ok": True, "tool_name": name, "result": result}
    except Exception as exc:
        return {
            "ok": False,
            "tool_name": name,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }


def _extract_function_calls(response: object) -> list[dict[str, Any]]:
    calls = []
    response_id = _get_response_id(response)
    for output_index, item in enumerate(_get_response_output(response)):
        if not _is_function_call_item(item):
            continue

        name = _get_item_value(item, "name")
        call_id = _get_item_value(item, "call_id") or _get_item_value(item, "id")
        item_id = _get_item_value(item, "id")
        arguments = _parse_tool_arguments(_get_item_value(item, "arguments"))
        if name and call_id:
            calls.append(
                {
                    "name": name,
                    "call_id": call_id,
                    "item_id": item_id,
                    "arguments": arguments,
                    "response_id": response_id,
                    "output_index": output_index,
                }
            )
    return calls


def _stream_function_call_from_event(event: object, item: object) -> dict[str, Any]:
    item_id = _get_item_value(item, "id")
    call_id = _get_item_value(item, "call_id") or item_id
    return {
        "name": _get_item_value(item, "name") or "tool",
        "call_id": call_id or "tool_call",
        "item_id": item_id,
        "arguments": _parse_tool_arguments(_get_item_value(item, "arguments")),
        "response_id": _get_item_value(event, "response_id"),
        "output_index": _get_item_value(event, "output_index"),
    }


def _is_function_call_item(item: object) -> bool:
    if _get_item_value(item, "type") == "function_call":
        return True
    return bool(_get_item_value(item, "name") and (_get_item_value(item, "call_id") or _get_item_value(item, "id")))


def _tool_call_was_seen(seen_keys: set[str], tool_call: dict[str, Any]) -> bool:
    return any(key in seen_keys for key in _tool_call_keys(tool_call))


def _remember_tool_call(seen_keys: set[str], tool_call: dict[str, Any]) -> None:
    seen_keys.update(_tool_call_keys(tool_call))


def _tool_call_keys(tool_call: dict[str, Any]) -> set[str]:
    keys = set()
    response_id = tool_call.get("response_id")
    output_index = tool_call.get("output_index")
    if response_id and output_index is not None:
        keys.add(f"response:{response_id}:output:{output_index}")
    if tool_call.get("call_id"):
        keys.add(f"call:{tool_call['call_id']}")
    if tool_call.get("item_id"):
        keys.add(f"item:{tool_call['item_id']}")
    return keys


def _get_response_output(response: object) -> list[Any]:
    if isinstance(response, dict):
        output = response.get("output", [])
    else:
        output = getattr(response, "output", [])
    return output if isinstance(output, list) else []


def _get_response_id(response: object) -> str | None:
    if isinstance(response, dict):
        response_id = response.get("id")
    else:
        response_id = getattr(response, "id", None)
    return response_id if isinstance(response_id, str) else None


def _get_item_value(item: object, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if isinstance(raw_arguments, str) and raw_arguments:
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _emit_event(
    on_event: AgentEventHandler | None,
    phase: AgentEventPhase,
    message: str,
    metadata: dict[str, Any],
    on_ag_ui_event: AgUiEventHandler | None = None,
    ag_ui_status_message_id: str | None = None,
) -> None:
    event: AgentEvent = {
        "type": "agent.status",
        "phase": phase,
        "message": message,
        "metadata": metadata,
    }
    if on_event is None:
        pass
    else:
        on_event(event)
    if on_ag_ui_event is not None and ag_ui_status_message_id:
        on_ag_ui_event(status_activity_snapshot_event(ag_ui_status_message_id, event))
        on_ag_ui_event(status_custom_event(event))


def _emit_ag_ui_event(on_ag_ui_event: AgUiEventHandler | None, event: AgUiEvent) -> None:
    if on_ag_ui_event is not None:
        on_ag_ui_event(event)


def _tool_execution_phase(tool_name: str) -> AgentEventPhase:
    if tool_name == "load_skill":
        return "loading_skill"
    if tool_name == "read_skill_file":
        return "reading_skill_file"
    if tool_name == "run_approved_skill_script":
        return "executing_script"
    return "executing_tool"


def _tool_call_message(tool_name: str) -> str:
    if tool_name == "load_skill":
        return "Selecting a service skill."
    if tool_name == "read_skill_file":
        return "Selecting a skill reference."
    if tool_name == "run_approved_skill_script":
        return "Requesting an approved skill script."
    return "Selecting an application tool."


def _tool_execution_message(tool_name: str) -> str:
    if tool_name == "load_skill":
        return "Loading service skill context."
    if tool_name == "read_skill_file":
        return "Reading an approved skill file."
    if tool_name == "run_approved_skill_script":
        return "Running an approved skill script."
    return "Executing an application tool."


def _tool_completed_message(tool_name: str, ok: bool) -> str:
    status = "completed" if ok else "failed"
    return f"Tool {status}: {tool_name}."


def _tool_result_metadata(round_index: int, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "round": round_index,
        "tool_name": tool_name,
        "ok": bool(result.get("ok")),
    }
    tool_result = result.get("result")
    if isinstance(tool_result, dict):
        if isinstance(tool_result.get("id"), str):
            metadata["skill_id"] = tool_result["id"]
        if isinstance(tool_result.get("skill_id"), str):
            metadata["skill_id"] = tool_result["skill_id"]
        if isinstance(tool_result.get("status"), str):
            metadata["status"] = tool_result["status"]
    return metadata


def _error_metadata(exc: Exception, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    if extra:
        metadata.update(extra)
    return metadata
