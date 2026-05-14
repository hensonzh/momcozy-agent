from __future__ import annotations

from typing import Any, Callable

from .contexts import DEFAULT_LOCALE, DEFAULT_TIMEZONE
from .tool_handlers.cards import create_card, create_form
from .tool_handlers.common import decode_json_argument_strings
from .tool_handlers.device import create_support_ticket_draft, search_device_manual
from .tool_handlers.handoff import generate_handoff_summary
from .tool_handlers.ibclc import create_ibclc_consult_card
from .tool_handlers.milk_management import execute_milk_management_tool
from .tool_handlers.profile import get_profile
from .tool_handlers.skill_runtime import (
    list_skills,
    load_skill,
    read_skill_file,
    run_approved_skill_script,
    search_skill_assets,
)
from .tool_schemas import FUNCTION_TOOLS
from .types import FunctionToolDefinition, RuntimeInputs, ToolDefinition, ToolName

ToolHandler = Callable[[dict[str, Any], RuntimeInputs], dict[str, Any]]

ALWAYS_ON_TOOLS: list[ToolName] = ["profile_get"]
SKILL_RUNTIME_TOOLS: list[ToolName] = ["list_skills", "load_skill", "search_skill_assets", "read_skill_file", "run_approved_skill_script"]
CORE_IMMEDIATE_TOOLS: list[ToolName] = [
    *ALWAYS_ON_TOOLS,
    *SKILL_RUNTIME_TOOLS,
    "ui_form_create",
    "ui_card_create",
    "ibclc_consult_card_create",
]
MILK_MANAGEMENT_TOOLS: list[ToolName] = [
    "milk_context_get",
    "milk_assessment_evaluate",
    "infant_growth_evaluate",
    "milk_plan_preview",
    "milk_plan_apply",
    "milk_plan_list",
    "milk_plan_get",
    "milk_plan_delete",
    "milk_plan_update",
    "milk_plan_regenerate_preview",
    "milk_plan_target_validate",
    "milk_plan_validate",
    "milk_records_range_get",
    "milk_record_create",
    "milk_record_update",
    "milk_record_delete",
    "milk_today_overview_get",
    "milk_today_summary_get",
    "milk_today_tasks_shift",
    "milk_today_tasks_confirm",
    "milk_calendar_day_get",
    "milk_calendar_range_get",
    "milk_calendar_adjustment_preview",
    "milk_calendar_adjustment_apply",
    "milk_calendar_range_update",
    "milk_calendar_item_update",
    "milk_calendar_item_delete",
]
MILK_MANAGEMENT_READ_ONLY_TOOLS: set[ToolName] = {
    "milk_context_get",
    "milk_assessment_evaluate",
    "infant_growth_evaluate",
    "milk_plan_preview",
    "milk_plan_list",
    "milk_plan_get",
    "milk_plan_regenerate_preview",
    "milk_plan_target_validate",
    "milk_plan_validate",
    "milk_records_range_get",
    "milk_today_overview_get",
    "milk_today_summary_get",
    "milk_calendar_day_get",
    "milk_calendar_range_get",
    "milk_calendar_adjustment_preview",
}

DEFERRED_TOOL_NAMESPACES: dict[str, dict[str, Any]] = {
    "care_handoffs": {
        "description": "用于专业支持流程的转接摘要生成工具。",
        "tool_names": ["handoff_summary_generate"],
    },
    "device_support": {
        "description": "用于吸奶器设备支持的工具，包括本地说明书/FAQ 检索和客服工单草稿。",
        "tool_names": ["device_manual_search", "support_ticket_draft_create"],
    },
    "milk_management": {
        "description": "用于奶量评估、任意时间段记录读取/修改、追奶/稳奶/减奶计划、计划执行情况读取和奶量 calendar 调整的工具。",
        "tool_names": MILK_MANAGEMENT_TOOLS,
    },
}

READ_ONLY_TOOL_NAMES = {
    "profile_get",
    "handoff_summary_generate",
    "ibclc_consult_card_create",
    "device_manual_search",
    "support_ticket_draft_create",
    *MILK_MANAGEMENT_READ_ONLY_TOOLS,
}

TOOL_HANDLERS: dict[ToolName, ToolHandler] = {
    "list_skills": list_skills,
    "load_skill": load_skill,
    "search_skill_assets": search_skill_assets,
    "read_skill_file": read_skill_file,
    "run_approved_skill_script": run_approved_skill_script,
    "ui_form_create": create_form,
    "ui_card_create": create_card,
    "ibclc_consult_card_create": create_ibclc_consult_card,
    "profile_get": get_profile,
    "handoff_summary_generate": generate_handoff_summary,
    "device_manual_search": search_device_manual,
    "support_ticket_draft_create": create_support_ticket_draft,
}
TOOL_HANDLERS.update({tool_name: execute_milk_management_tool for tool_name in MILK_MANAGEMENT_TOOLS})


def select_runtime_tools() -> list[ToolDefinition]:
    tools: list[ToolDefinition] = [{"type": "tool_search"}]
    tools.extend(FUNCTION_TOOLS[name] for name in CORE_IMMEDIATE_TOOLS)
    tools.extend(_deferred_tool_namespaces())

    return tools


def execute_tool(name: str, arguments: dict[str, Any], inputs: RuntimeInputs | None = None) -> dict[str, Any]:
    args = decode_json_argument_strings(arguments)
    runtime_inputs: RuntimeInputs = inputs or {"user_message": "", "locale": DEFAULT_LOCALE, "timezone": DEFAULT_TIMEZONE, "message_sent_at": ""}
    handler_args = dict(args)
    handler_args["_tool_name"] = name

    handler = TOOL_HANDLERS.get(name)  # type: ignore[arg-type]
    if handler is not None:
        return handler(handler_args, runtime_inputs)
    raise ValueError(f"Unknown or unavailable tool: {name}")


def execute_business_tool(name: str, arguments: dict[str, Any], inputs: RuntimeInputs | None = None) -> dict[str, Any]:
    if name in SKILL_RUNTIME_TOOLS:
        raise ValueError(f"{name} is a skill runtime tool; use execute_tool instead.")
    return execute_tool(name, arguments, inputs)


def _deferred_tool_namespaces() -> list[ToolDefinition]:
    namespaces: list[ToolDefinition] = []
    for namespace_name, namespace in DEFERRED_TOOL_NAMESPACES.items():
        namespaces.append(
            {
                "type": "namespace",
                "name": namespace_name,
                "description": namespace["description"],
                "tools": [_deferred_tool(tool_name) for tool_name in namespace["tool_names"]],
            }
        )
    return namespaces


def _deferred_tool(tool_name: ToolName) -> FunctionToolDefinition:
    tool = dict(FUNCTION_TOOLS[tool_name])
    tool["defer_loading"] = True
    return tool  # type: ignore[return-value]
