from __future__ import annotations

from typing import Any

from ..services.milk_management.calendar import (
    apply_calendar_adjustment,
    delete_calendar_item,
    get_calendar_day,
    preview_calendar_adjustment,
    update_calendar_item,
)
from ..services.milk_management.context import get_milk_context
from ..services.milk_management.growth import evaluate_infant_growth
from ..services.milk_management.plan import (
    apply_milk_plan,
    delete_milk_plan,
    get_milk_plan,
    list_milk_plans,
    preview_milk_plan,
    regenerate_milk_plan_preview,
    update_milk_plan,
    validate_milk_plan,
    validate_milk_plan_target,
)
from ..services.milk_management.assessment import evaluate_milk_status
from ..services.milk_management.today import (
    confirm_today_tasks,
    get_today_overview,
    get_today_summary,
    shift_today_tasks,
)
from ..types import FunctionToolDefinition

USER_ID = {"type": "string", "description": "Application user ID."}
ISO_DATE = {"type": "string", "description": "ISO-8601 date, for example 2026-05-07."}
JSON_OBJECT_STRING = {
    "type": "string",
    "description": "Free-form JSON object encoded as a string. Use \"{}\" when no fields are needed.",
}

MILK_MANAGEMENT_TOOL_NAMES = {
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
    "milk_today_overview_get",
    "milk_today_summary_get",
    "milk_today_tasks_shift",
    "milk_today_tasks_confirm",
    "milk_calendar_day_get",
    "milk_calendar_adjustment_preview",
    "milk_calendar_adjustment_apply",
    "milk_calendar_item_update",
    "milk_calendar_item_delete",
}


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    types = _schema_types(schema)
    if "object" in types:
        schema.setdefault("additionalProperties", False)
        schema["required"] = list(schema.get("properties", {}).keys())
        for property_schema in schema.get("properties", {}).values():
            if isinstance(property_schema, dict):
                _strict_schema(property_schema)
    if "array" in types and isinstance(schema.get("items"), dict):
        _strict_schema(schema["items"])
    return schema


def _schema_types(schema: dict[str, Any]) -> set[str]:
    type_value = schema.get("type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, list):
        return {item for item in type_value if isinstance(item, str)}
    return set()


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(schema)
    type_value = cloned.get("type")
    if isinstance(type_value, str):
        cloned["type"] = [type_value, "null"] if type_value != "null" else type_value
    elif isinstance(type_value, list):
        cloned["type"] = type_value if "null" in type_value else [*type_value, "null"]
    else:
        cloned["type"] = ["null"]
    return cloned


def _function_tool(name: str, description: str, properties: dict[str, Any]) -> FunctionToolDefinition:
    return {
        "type": "function",
        "name": name,  # type: ignore[typeddict-item]
        "description": description,
        "strict": True,
        "parameters": _strict_schema({"type": "object", "properties": properties}),
    }


MILK_MANAGEMENT_FUNCTION_TOOLS: dict[str, FunctionToolDefinition] = {
    "milk_context_get": _function_tool(
        "milk_context_get",
        "Read milk-management context for one user, including profiles and latest plan metadata. No side effects.",
        {"user_id": USER_ID},
    ),
    "milk_assessment_evaluate": _function_tool(
        "milk_assessment_evaluate",
        "Evaluate milk status from user profile, infant profile, pumping logs, feeding logs, and milk knowledge references. No side effects.",
        {
            "user_id": USER_ID,
            "as_of_time": _nullable({"type": "string", "description": "Optional ISO-8601 evaluation time."}),
            "window_days": {"type": "integer", "description": "Lookback days. Use 1 for yesterday-only assessment."},
            "include_today": {"type": "boolean", "description": "Whether to include current-day partial records."},
        },
    ),
    "infant_growth_evaluate": _function_tool(
        "infant_growth_evaluate",
        "Evaluate baby growth from infant profile, growth logs, and growth reference data. No side effects.",
        {
            "user_id": USER_ID,
            "infant_id": _nullable({"type": "integer", "description": "Optional infant id. Pass null to evaluate the default/all infants."}),
            "as_of_time": _nullable({"type": "string", "description": "Optional ISO-8601 evaluation time."}),
        },
    ),
    "milk_plan_preview": _function_tool(
        "milk_plan_preview",
        "Generate an increase, maintain, or decrease milk plan draft. No database writes; user confirmation is required before apply.",
        {
            "user_id": USER_ID,
            "plan_type": {"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]},
            "plan_days": _nullable({"type": "integer"}),
            "custom_target_daily_ml": _nullable({"type": "number"}),
            "as_of_time": _nullable({"type": "string"}),
            "options": _nullable(JSON_OBJECT_STRING),
        },
    ),
    "milk_plan_apply": _function_tool(
        "milk_plan_apply",
        "Persist a user-confirmed milk plan to milk_plan and expand its schedule into calendar. Has side effects; call only after explicit confirmation.",
        {
            "user_id": USER_ID,
            "confirmed_plan": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_plan_list": _function_tool(
        "milk_plan_list",
        "List saved milk plans for one user. No side effects.",
        {
            "user_id": USER_ID,
            "plan_type": _nullable({"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]}),
            "limit": {"type": "integer"},
        },
    ),
    "milk_plan_get": _function_tool(
        "milk_plan_get",
        "Read one saved milk plan, or the latest saved plan when plan_id is null. No side effects.",
        {
            "user_id": USER_ID,
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_plan_delete": _function_tool(
        "milk_plan_delete",
        "Delete a saved milk plan and optionally its generated calendar items. Has side effects; call only after explicit confirmation.",
        {
            "user_id": USER_ID,
            "plan_id": {"type": "integer"},
            "idempotency_key": {"type": "string"},
            "delete_calendar_items": {"type": "boolean"},
        },
    ),
    "milk_plan_update": _function_tool(
        "milk_plan_update",
        "Update saved milk plan metadata or replace it with an edited plan payload. Has side effects; call only after explicit confirmation.",
        {
            "user_id": USER_ID,
            "plan_id": {"type": "integer"},
            "patch": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
            "reexpand_calendar": {"type": "boolean"},
        },
    ),
    "milk_plan_regenerate_preview": _function_tool(
        "milk_plan_regenerate_preview",
        "Regenerate a milk plan draft from an existing plan or supplied type. No database writes; user confirmation is required before apply/update.",
        {
            "user_id": USER_ID,
            "plan_id": _nullable({"type": "integer"}),
            "plan_type": _nullable({"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]}),
            "plan_days": _nullable({"type": "integer"}),
            "custom_target_daily_ml": _nullable({"type": "number"}),
            "as_of_time": _nullable({"type": "string"}),
            "options": _nullable(JSON_OBJECT_STRING),
        },
    ),
    "milk_plan_target_validate": _function_tool(
        "milk_plan_target_validate",
        "Validate an increase, maintain, or decrease milk target against current milk assessment and reference bounds. No side effects.",
        {
            "user_id": USER_ID,
            "plan_type": {"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]},
            "target_daily_ml": _nullable({"type": "number"}),
            "delta_ml": _nullable({"type": "number", "description": "Desired increase/decrease amount in ml/day when target_daily_ml is not supplied."}),
            "as_of_time": _nullable({"type": "string"}),
        },
    ),
    "milk_plan_validate": _function_tool(
        "milk_plan_validate",
        "Validate a full milk plan draft or edited saved plan before apply/update. No side effects.",
        {
            "user_id": USER_ID,
            "plan": JSON_OBJECT_STRING,
        },
    ),
    "milk_today_overview_get": _function_tool(
        "milk_today_overview_get",
        "Read today's milk-management calendar overview: total tasks, completion count, pending count, and items. No side effects.",
        {
            "user_id": USER_ID,
            "target_date": _nullable(ISO_DATE),
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_today_summary_get": _function_tool(
        "milk_today_summary_get",
        "Read today's completion summary with calendar, pumping, and feeding details. No side effects.",
        {
            "user_id": USER_ID,
            "target_date": _nullable(ISO_DATE),
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_today_tasks_shift": _function_tool(
        "milk_today_tasks_shift",
        "Shift today's calendar tasks by a number of minutes. Has side effects; call only after explicit confirmation.",
        {
            "user_id": USER_ID,
            "target_date": _nullable(ISO_DATE),
            "shift_minutes": {"type": "integer"},
            "from_time": _nullable({"type": "string", "description": "Only shift tasks at or after this time, for example 14:00."}),
            "plan_id": _nullable({"type": "integer"}),
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_today_tasks_confirm": _function_tool(
        "milk_today_tasks_confirm",
        "Mark today's milk-pumping tasks as finished. Has side effects; call only after explicit confirmation.",
        {
            "user_id": USER_ID,
            "target_date": _nullable(ISO_DATE),
            "plan_id": _nullable({"type": "integer"}),
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_day_get": _function_tool(
        "milk_calendar_day_get",
        "Read one day of milk-management calendar items. No side effects.",
        {
            "user_id": USER_ID,
            "target_date": ISO_DATE,
            "plan_id": _nullable({"type": "integer"}),
            "item_type": _nullable({"type": "string", "enum": ["吸奶", "亲喂", "自定义"]}),
        },
    ),
    "milk_calendar_adjustment_preview": _function_tool(
        "milk_calendar_adjustment_preview",
        "Preview calendar changes for a new user event such as school pickup or a meeting. No database writes; user confirmation is required before apply.",
        {
            "user_id": USER_ID,
            "target_date": ISO_DATE,
            "event_start_time": {"type": "string", "description": "Start time such as 09:00 or full ISO datetime."},
            "event_end_time": _nullable({"type": "string", "description": "End time such as 09:30. Pass null if duration_minutes is provided."}),
            "duration_minutes": _nullable({"type": "integer"}),
            "content": {"type": "string"},
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_calendar_adjustment_apply": _function_tool(
        "milk_calendar_adjustment_apply",
        "Apply a user-confirmed calendar adjustment proposal. Has side effects; call only after explicit confirmation.",
        {
            "user_id": USER_ID,
            "target_date": ISO_DATE,
            "proposal": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_item_update": _function_tool(
        "milk_calendar_item_update",
        "Update one calendar item, such as finish status, time, content, or type. Has side effects.",
        {
            "user_id": USER_ID,
            "item_id": {"type": "integer"},
            "patch": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_item_delete": _function_tool(
        "milk_calendar_item_delete",
        "Delete one calendar item. Has side effects; use only after the target item is clear.",
        {
            "user_id": USER_ID,
            "item_id": {"type": "integer"},
            "idempotency_key": {"type": "string"},
        },
    ),
}


def execute_milk_management_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "milk_context_get":
        return dict(get_milk_context(**arguments))
    if name == "milk_assessment_evaluate":
        return dict(evaluate_milk_status(**arguments))
    if name == "infant_growth_evaluate":
        return dict(evaluate_infant_growth(**arguments))
    if name == "milk_plan_preview":
        return dict(preview_milk_plan(**arguments))
    if name == "milk_plan_apply":
        return dict(apply_milk_plan(**arguments))
    if name == "milk_plan_list":
        return dict(list_milk_plans(**arguments))
    if name == "milk_plan_get":
        return dict(get_milk_plan(**arguments))
    if name == "milk_plan_delete":
        return dict(delete_milk_plan(**arguments))
    if name == "milk_plan_update":
        return dict(update_milk_plan(**arguments))
    if name == "milk_plan_regenerate_preview":
        return dict(regenerate_milk_plan_preview(**arguments))
    if name == "milk_plan_target_validate":
        return dict(validate_milk_plan_target(**arguments))
    if name == "milk_plan_validate":
        return dict(validate_milk_plan(**arguments))
    if name == "milk_today_overview_get":
        return dict(get_today_overview(**arguments))
    if name == "milk_today_summary_get":
        return dict(get_today_summary(**arguments))
    if name == "milk_today_tasks_shift":
        return dict(shift_today_tasks(**arguments))
    if name == "milk_today_tasks_confirm":
        return dict(confirm_today_tasks(**arguments))
    if name == "milk_calendar_day_get":
        return dict(get_calendar_day(**arguments))
    if name == "milk_calendar_adjustment_preview":
        return dict(preview_calendar_adjustment(**arguments))
    if name == "milk_calendar_adjustment_apply":
        return dict(apply_calendar_adjustment(**arguments))
    if name == "milk_calendar_item_update":
        return dict(update_calendar_item(**arguments))
    if name == "milk_calendar_item_delete":
        return dict(delete_calendar_item(**arguments))
    raise ValueError(f"Unknown milk-management tool: {name}")
