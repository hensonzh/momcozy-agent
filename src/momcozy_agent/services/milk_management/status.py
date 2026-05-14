from __future__ import annotations

from datetime import datetime
from typing import Any

from .. import data_store
from .feeding import assess_feeding_demand_reference
from .schemas import ServiceResult, error_result, norm_text, ok_result, parse_datetime, to_int

STATUS_SECTIONS = {"all", "overview", "today", "trend", "growth", "tasks"}


def query_milk_status(
    *,
    user_id: str,
    section: str = "all",
    target_date: str | None = None,
    trend_days: int = 30,
    growth_history_limit: int = 10,
    include_tasks: bool = True,
) -> ServiceResult:
    uid = norm_text(user_id)
    if not uid:
        return error_result("missing_user_id", "缺少 user_id，无法读取奶量状态。")

    selected_section = norm_text(section) or "all"
    if selected_section not in STATUS_SECTIONS:
        return error_result("invalid_status_section", f"Unsupported status section: {section}")

    date_text = _date_text(target_date)
    days = min(max(to_int(trend_days, 30), 1), 30)
    history_limit = min(max(to_int(growth_history_limit, 10), 1), 50)

    data: dict[str, Any] = {
        "user_id": uid,
        "section": selected_section,
        "target_date": date_text,
        "missing": [],
    }

    if selected_section in {"all", "overview"}:
        info = data_store.get_mom_baby_info(uid)
        data["mom_baby_info"] = info or {}
        if not info:
            data["missing"].append("mom_baby_info")
        data["feeding_reference"] = assess_feeding_demand_reference(user_id=uid, as_of_date=date_text)

    if selected_section in {"all", "today"}:
        today = data_store.get_mom_baby_today_summary(uid, date_text)
        data["today"] = today or {}
        if today is None:
            data["missing"].append("today_summary")
        data["feeding_reference"] = assess_feeding_demand_reference(user_id=uid, as_of_date=date_text)

    if selected_section in {"all", "trend"}:
        pump_info = data_store.pump_info(uid)
        trend_items = list(pump_info.get("lactation_info_list") or [])[-days:]
        data["pump_info"] = {key: value for key, value in pump_info.items() if key != "lactation_info_list"}
        data["trend"] = {
            "days": len(trend_items),
            "items": trend_items,
        }

    if selected_section in {"all", "growth"}:
        history = data_store.growth_records_for_user(uid)
        data["growth"] = {
            "latest": data_store.latest_growth_record_for_user(uid) or {},
            "history": history[:history_limit],
            "history_count": len(history),
            "history_limit": history_limit,
        }
        if not history:
            data["missing"].append("growth_history")

    if include_tasks or selected_section == "tasks":
        tasks = data_store.query_plan_tasks(user_id=uid, target_date=date_text)
        data["tasks"] = tasks or {"plan_type": "None", "task_list": []}
        if tasks is None:
            data["missing"].append("tasks")

    loaded = sorted(key for key in data.keys() if key not in {"user_id", "section", "target_date", "missing"})
    return ok_result(
        "milk_status_loaded",
        "已读取奶量状态聚合信息。",
        {
            **data,
            "loaded_sections": loaded,
        },
    )


def _date_text(value: Any) -> str:
    parsed = parse_datetime(value) if value else datetime.now()
    if parsed is None:
        token = norm_text(value)
        return token[:10] if token else datetime.now().date().isoformat()
    return parsed.date().isoformat()
