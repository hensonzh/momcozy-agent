from __future__ import annotations

import json
import os
from typing import Any

from ..services.milk_management.assessment import evaluate_milk_status
from ..services.milk_management.calendar import (
    apply_calendar_adjustment,
    delete_calendar_item,
    get_calendar_range,
    get_calendar_day,
    preview_calendar_adjustment,
    update_calendar_range,
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
from ..services.milk_management.records import (
    create_record,
    delete_record,
    get_records_range,
    update_record,
)
from ..services.milk_management.today import (
    confirm_today_tasks,
    get_today_overview,
    get_today_summary,
    shift_today_tasks,
)
from ..types import RuntimeInputs

CALENDAR_UI_REQUIRED_MESSAGE = "好的，这个需要您回到主界面的日历中操作完成，并记录具体时间和奶量哦。这样可以帮助我们更准确地评估您的泌乳状态。"


def execute_milk_management_tool(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    name = str(args.get("_tool_name") or "")
    arguments = _with_user_id(args, inputs)

    if name == "milk_context_get":
        return dict(get_milk_context(**_pick(arguments, "user_id")))
    if name == "milk_assessment_evaluate":
        return dict(evaluate_milk_status(**_pick(arguments, "user_id", "as_of_time", "window_days", "include_today")))
    if name == "infant_growth_evaluate":
        return dict(evaluate_infant_growth(**_pick(arguments, "user_id", "infant_id", "as_of_time")))
    if name == "milk_plan_preview":
        return dict(preview_milk_plan(**_pick(arguments, "user_id", "plan_type", "plan_days", "custom_target_daily_ml", "as_of_time", "options")))
    if name == "milk_plan_apply":
        return dict(apply_milk_plan(**_pick(arguments, "user_id", "confirmed_plan", "idempotency_key")))
    if name == "milk_plan_list":
        return dict(list_milk_plans(**_pick(arguments, "user_id", "plan_type", "limit")))
    if name == "milk_plan_get":
        return dict(get_milk_plan(**_pick(arguments, "user_id", "plan_id")))
    if name == "milk_plan_delete":
        return dict(delete_milk_plan(**_pick(arguments, "user_id", "plan_id", "idempotency_key", "delete_calendar_items")))
    if name == "milk_plan_update":
        return dict(update_milk_plan(**_pick(arguments, "user_id", "plan_id", "patch", "idempotency_key", "reexpand_calendar")))
    if name == "milk_plan_regenerate_preview":
        return dict(
            regenerate_milk_plan_preview(
                **_pick(arguments, "user_id", "plan_id", "plan_type", "plan_days", "custom_target_daily_ml", "as_of_time", "options")
            )
        )
    if name == "milk_plan_target_validate":
        return dict(validate_milk_plan_target(**_pick(arguments, "user_id", "plan_type", "target_daily_ml", "delta_ml", "as_of_time")))
    if name == "milk_plan_validate":
        return dict(validate_milk_plan(**_pick(arguments, "user_id", "plan")))
    if name == "milk_records_range_get":
        return dict(
            get_records_range(
                **_pick(arguments, "user_id", "start_at", "end_at", "record_scope", "include_raw_records", "summary_granularity", "limit")
            )
        )
    if name == "milk_record_create":
        return dict(
            create_record(
                **_pick(arguments, "user_id", "record_kind", "occurred_at", "amount_ml", "duration_minutes", "infant_id", "title", "idempotency_key")
            )
        )
    if name == "milk_record_update":
        return dict(update_record(**_pick(arguments, "user_id", "record_kind", "record_id", "patch", "idempotency_key")))
    if name == "milk_record_delete":
        return dict(delete_record(**_pick(arguments, "user_id", "record_kind", "record_id", "idempotency_key")))
    if name == "milk_today_overview_get":
        return dict(get_today_overview(**_pick(arguments, "user_id", "target_date", "plan_id")))
    if name == "milk_today_summary_get":
        return dict(get_today_summary(**_pick(arguments, "user_id", "target_date", "plan_id")))
    if name == "milk_today_tasks_shift":
        return dict(shift_today_tasks(**_pick(arguments, "user_id", "target_date", "shift_minutes", "from_time", "plan_id", "idempotency_key")))
    if name == "milk_today_tasks_confirm":
        if not _llm_calendar_finish_updates_enabled():
            return _calendar_ui_required_result()
        return dict(confirm_today_tasks(**_pick(arguments, "user_id", "target_date", "plan_id", "idempotency_key")))
    if name == "milk_calendar_day_get":
        return dict(get_calendar_day(**_pick(arguments, "user_id", "target_date", "plan_id", "item_type")))
    if name == "milk_calendar_range_get":
        return dict(get_calendar_range(**_pick(arguments, "user_id", "start_at", "end_at", "plan_id", "item_type", "include_items", "limit")))
    if name == "milk_calendar_adjustment_preview":
        return dict(
            preview_calendar_adjustment(
                **_pick(
                    arguments,
                    "user_id",
                    "target_date",
                    "event_start_time",
                    "event_end_time",
                    "duration_minutes",
                    "content",
                    "item_type",
                    "plan_id",
                )
            )
        )
    if name == "milk_calendar_adjustment_apply":
        return dict(apply_calendar_adjustment(**_pick(arguments, "user_id", "target_date", "proposal", "idempotency_key")))
    if name == "milk_calendar_range_update":
        return dict(
            update_calendar_range(
                **_pick(arguments, "user_id", "start_at", "end_at", "operation", "patch", "plan_id", "item_type", "idempotency_key")
            )
        )
    if name == "milk_calendar_item_update":
        if _calendar_item_update_has_finish(arguments) and not _llm_calendar_finish_updates_enabled():
            return _calendar_ui_required_result()
        return dict(update_calendar_item(**_calendar_item_update_arguments(arguments)))
    if name == "milk_calendar_item_delete":
        return dict(delete_calendar_item(**_pick(arguments, "user_id", "item_id")))
    raise ValueError(f"Unknown milk-management tool: {name}")


def _with_user_id(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    arguments = {key: value for key, value in args.items() if key != "_tool_name"}
    if arguments.get("user_id"):
        return arguments
    user_id = inputs.get("user_id") or inputs.get("user_profile", {}).get("user_id")
    if not user_id:
        raise ValueError("Milk-management tools require a user_id in runtime inputs.")
    arguments["user_id"] = str(user_id)
    return arguments


def _pick(arguments: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {key: arguments[key] for key in keys if key in arguments}


def _calendar_item_update_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    normalized = _pick(arguments, "user_id", "item_id")
    patch = arguments.get("patch")
    if patch:
        patch_data = _parse_json_object(patch)
        for key in ("start_time", "end_time", "content", "item_type", "finish"):
            if key in patch_data and key not in normalized:
                normalized[key] = patch_data[key]
        if "type" in patch_data and "item_type" not in normalized:
            normalized["item_type"] = patch_data["type"]
    for key in ("start_time", "end_time", "content", "item_type", "finish"):
        if key in arguments and key not in normalized:
            normalized[key] = arguments[key]
    return normalized


def _calendar_item_update_has_finish(arguments: dict[str, Any]) -> bool:
    if "finish" in arguments:
        return True
    patch = arguments.get("patch")
    if not patch:
        return False
    patch_data = _parse_json_object(patch)
    return "finish" in patch_data


def _llm_calendar_finish_updates_enabled() -> bool:
    return str(os.getenv("MOMCOZY_LLM_CALENDAR_FINISH_UPDATE_ENABLED", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _calendar_ui_required_result() -> dict[str, Any]:
    return {
        "ok": False,
        "status": "calendar_ui_required",
        "summary": CALENDAR_UI_REQUIRED_MESSAGE,
        "data": {"message": CALENDAR_UI_REQUIRED_MESSAGE},
    }


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
