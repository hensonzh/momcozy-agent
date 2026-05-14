from __future__ import annotations

import json
import os
from typing import Any

from ..services.milk_management.assessment import evaluate_milk_status
from ..services.milk_management.calendar import (
    apply_calendar_adjustment,
    delete_calendar_item,
    get_calendar_range,
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
    get_today_overview,
    get_today_summary,
)
from ..types import RuntimeInputs

CALENDAR_UI_REQUIRED_MESSAGE = "好的，这个需要您回到主界面的日历中操作完成，并记录具体时间和奶量哦。这样可以帮助我们更准确地评估您的泌乳状态。"


def execute_milk_management_tool(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    name = str(args.get("_tool_name") or "")
    arguments = _with_user_id(args, inputs)

    if name == "milk_snapshot_get":
        return dict(get_milk_context(**_pick(arguments, "user_id")))
    if name == "milk_records_query":
        return dict(
            get_records_range(
                **_pick(arguments, "user_id", "start_at", "end_at", "record_scope", "include_raw_records", "summary_granularity", "limit")
            )
        )
    if name == "milk_record_mutate":
        return _mutate_record(arguments)
    if name == "milk_plan_query":
        return _query_plan(arguments)
    if name == "milk_plan_mutate":
        return _mutate_plan(arguments)
    if name == "milk_calendar_query":
        return _query_calendar(arguments)
    if name == "milk_calendar_change_preview":
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
    if name == "milk_calendar_mutate":
        return _mutate_calendar(arguments)
    if name == "milk_assessment_evaluate":
        return dict(evaluate_milk_status(**_pick(arguments, "user_id", "as_of_time", "window_days", "include_today")))
    if name == "infant_growth_evaluate":
        return dict(evaluate_infant_growth(**_pick(arguments, "user_id", "infant_id", "as_of_time")))
    if name == "milk_plan_preview":
        return _preview_plan(arguments)
    raise ValueError(f"Unknown milk-management tool: {name}")


def _preview_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    plan_type = arguments.get("plan_type")
    target_daily_ml = arguments.get("target_daily_ml")
    if target_daily_ml is None:
        target_daily_ml = arguments.get("custom_target_daily_ml")
    delta_ml = arguments.get("delta_ml")
    source_plan_id = arguments.get("source_plan_id") or arguments.get("plan_id")

    target_validation: dict[str, Any] | None = None
    if (target_daily_ml is not None or delta_ml is not None) and plan_type is not None:
        target_validation = dict(
            validate_milk_plan_target(
                user_id=arguments["user_id"],
                plan_type=plan_type,
                target_daily_ml=target_daily_ml,
                delta_ml=delta_ml,
                as_of_time=arguments.get("as_of_time"),
            )
        )
        validation_data = target_validation.get("data") if isinstance(target_validation.get("data"), dict) else {}
        if validation_data.get("valid") is False:
            return {
                "ok": False,
                "status": "milk_plan_target_invalid",
                "summary": target_validation.get("summary", "计划目标不符合当前边界。"),
                "data": {"target_validation": validation_data},
            }
        if target_daily_ml is None and validation_data.get("target_daily_ml") is not None:
            target_daily_ml = validation_data.get("target_daily_ml")

    if source_plan_id is not None:
        preview = dict(
            regenerate_milk_plan_preview(
                user_id=arguments["user_id"],
                plan_id=source_plan_id,
                plan_type=plan_type,
                plan_days=arguments.get("plan_days"),
                custom_target_daily_ml=target_daily_ml,
                as_of_time=arguments.get("as_of_time"),
                options=arguments.get("options"),
            )
        )
    else:
        if plan_type is None:
            return {
                "ok": False,
                "status": "milk_plan_preview_missing_plan_type",
                "summary": "缺少 plan_type，无法生成新的奶量计划草稿。",
                "data": {"missing_fields": ["plan_type"]},
            }
        preview = dict(
            preview_milk_plan(
                user_id=arguments["user_id"],
                plan_type=plan_type,
                plan_days=arguments.get("plan_days"),
                custom_target_daily_ml=target_daily_ml,
                as_of_time=arguments.get("as_of_time"),
                options=arguments.get("options"),
            )
        )

    if target_validation:
        data = preview.setdefault("data", {})
        if isinstance(data, dict):
            data["target_validation"] = target_validation.get("data", {})
    return preview


def _query_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    plan_id = arguments.get("plan_id")
    if plan_id is not None:
        return dict(get_milk_plan(user_id=arguments["user_id"], plan_id=plan_id))
    return dict(
        list_milk_plans(
            user_id=arguments["user_id"],
            plan_type=arguments.get("plan_type"),
            limit=arguments.get("limit", 10),
        )
    )


def _mutate_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    operation = _operation(arguments)
    if operation == "create":
        plan = arguments.get("confirmed_plan")
        validation = dict(validate_milk_plan(user_id=arguments["user_id"], plan=plan))
        validation_data = validation.get("data") if isinstance(validation.get("data"), dict) else {}
        if not validation.get("ok") or validation_data.get("valid") is False:
            return {
                "ok": False,
                "status": "milk_plan_invalid",
                "summary": validation.get("summary", "计划校验未通过。"),
                "data": {"validation": validation_data},
            }
        result = dict(apply_milk_plan(user_id=arguments["user_id"], confirmed_plan=plan, idempotency_key=arguments["idempotency_key"]))
        result.setdefault("data", {})
        if isinstance(result["data"], dict):
            result["data"]["validation"] = validation_data
        return result
    if operation == "update":
        plan = _plan_from_patch_for_validation(arguments.get("patch"))
        if plan:
            validation = dict(validate_milk_plan(user_id=arguments["user_id"], plan=plan))
            validation_data = validation.get("data") if isinstance(validation.get("data"), dict) else {}
            if not validation.get("ok") or validation_data.get("valid") is False:
                return {
                    "ok": False,
                    "status": "milk_plan_invalid",
                    "summary": validation.get("summary", "计划校验未通过。"),
                    "data": {"validation": validation_data},
                }
        return dict(
            update_milk_plan(
                user_id=arguments["user_id"],
                plan_id=arguments.get("plan_id"),
                patch=arguments.get("patch"),
                idempotency_key=arguments["idempotency_key"],
                reexpand_calendar=bool(arguments.get("reexpand_calendar")),
            )
        )
    if operation == "delete":
        return dict(
            delete_milk_plan(
                user_id=arguments["user_id"],
                plan_id=arguments.get("plan_id"),
                idempotency_key=arguments["idempotency_key"],
                delete_calendar_items=bool(arguments.get("delete_calendar_items")),
            )
        )
    raise ValueError(f"Unsupported milk_plan_mutate operation: {operation}")


def _mutate_record(arguments: dict[str, Any]) -> dict[str, Any]:
    operation = _operation(arguments)
    if operation == "create":
        return dict(
            create_record(
                **_pick(arguments, "user_id", "record_kind", "occurred_at", "amount_ml", "duration_minutes", "infant_id", "title", "idempotency_key")
            )
        )
    if operation == "update":
        return dict(update_record(**_pick(arguments, "user_id", "record_kind", "record_id", "patch", "idempotency_key")))
    if operation == "delete":
        return dict(delete_record(**_pick(arguments, "user_id", "record_kind", "record_id", "idempotency_key")))
    raise ValueError(f"Unsupported milk_record_mutate operation: {operation}")


def _query_calendar(arguments: dict[str, Any]) -> dict[str, Any]:
    query_mode = str(arguments.get("query_mode") or "range").strip()
    if query_mode == "today_overview":
        return dict(get_today_overview(**_pick(arguments, "user_id", "target_date", "plan_id")))
    if query_mode == "today_summary":
        return dict(get_today_summary(**_pick(arguments, "user_id", "target_date", "plan_id")))
    return dict(
        get_calendar_range(
            user_id=arguments["user_id"],
            start_at=arguments.get("start_at") or arguments.get("target_date"),
            end_at=arguments.get("end_at") or arguments.get("target_date"),
            plan_id=arguments.get("plan_id"),
            item_type=arguments.get("item_type"),
            include_items=bool(arguments.get("include_items")),
            limit=arguments.get("limit", 200),
        )
    )


def _mutate_calendar(arguments: dict[str, Any]) -> dict[str, Any]:
    operation = _operation(arguments)
    if operation == "apply_adjustment":
        return dict(apply_calendar_adjustment(**_pick(arguments, "user_id", "target_date", "proposal", "idempotency_key")))
    if operation in {"range_shift", "range_delete", "patch_items"}:
        mapped_operation = {"range_shift": "shift", "range_delete": "delete", "patch_items": "patch_items"}[operation]
        return dict(
            update_calendar_range(
                user_id=arguments["user_id"],
                start_at=arguments.get("start_at"),
                end_at=arguments.get("end_at"),
                operation=mapped_operation,
                patch=arguments.get("patch"),
                plan_id=arguments.get("plan_id"),
                item_type=arguments.get("item_type"),
                idempotency_key=arguments["idempotency_key"],
            )
        )
    if operation == "update_item":
        if _calendar_item_update_has_finish(arguments) and not _llm_calendar_finish_updates_enabled():
            return _calendar_ui_required_result()
        return dict(update_calendar_item(**_calendar_item_update_arguments(arguments)))
    if operation == "delete_item":
        return dict(delete_calendar_item(user_id=arguments["user_id"], item_id=arguments.get("item_id")))
    raise ValueError(f"Unsupported milk_calendar_mutate operation: {operation}")


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


def _operation(arguments: dict[str, Any]) -> str:
    return str(arguments.get("operation") or "").strip()


def _plan_from_patch_for_validation(patch: Any) -> dict[str, Any]:
    patch_data = _parse_json_object(patch)
    for key in ("confirmed_plan", "plan", "draft"):
        value = patch_data.get(key)
        if isinstance(value, dict):
            return value
    plan_payload = patch_data.get("plan_payload")
    if isinstance(plan_payload, dict) and isinstance(plan_payload.get("plan"), dict):
        return plan_payload["plan"]
    return {}


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
