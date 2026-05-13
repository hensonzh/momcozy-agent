from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from .. import data_store
from .db import execute, fetch_all, fetch_one, transaction
from .schemas import (
    CALENDAR_TYPE_CUSTOM,
    CALENDAR_TYPE_NURSING,
    CALENDAR_TYPE_PUMP,
    CalendarItem,
    ServiceResult,
    error_result,
    hhmm,
    norm_text,
    ok_result,
    parse_datetime,
    to_bool,
    to_int,
)

VALID_CALENDAR_TYPES = {CALENDAR_TYPE_PUMP, CALENDAR_TYPE_NURSING, CALENDAR_TYPE_CUSTOM}


def get_calendar_day(
    *,
    user_id: str,
    target_date: str,
    plan_id: int | None = None,
    item_type: str | None = None,
) -> ServiceResult:
    uid = str(user_id or "").strip()
    date = str(target_date or "").strip()
    if not uid or not date:
        return error_result("missing_required_field", "user_id and target_date are required.")

    params: list[Any] = [uid, date]
    clauses = ["user_id = ?", "date = ?"]
    if plan_id is not None:
        clauses.append("COALESCE(plan_id, 0) = ?")
        params.append(int(plan_id))
    if item_type:
        if item_type not in VALID_CALENDAR_TYPES:
            return error_result("invalid_calendar_type", f"Unsupported calendar type: {item_type}")
        clauses.append("type = ?")
        params.append(item_type)

    rows = fetch_all(
        f"""
        SELECT item_id, user_id, plan_id, date, task_id, start_time, end_time,
               content, type, source, is_milk_pump, finish, created_at, modified_at
        FROM calendar
        WHERE {" AND ".join(clauses)}
        ORDER BY COALESCE(start_time, ''), COALESCE(task_id, item_id), item_id
        """,
        params,
    )
    items = [_normalize_calendar_row(row) for row in rows]
    completed = len([item for item in items if item.get("finish")])
    return ok_result(
        "calendar_day_loaded",
        data={
            "user_id": uid,
            "target_date": date,
            "items": items,
            "summary": {
                "total_count": len(items),
                "completed_count": completed,
                "pending_count": max(len(items) - completed, 0),
            },
        },
    )


def preview_calendar_adjustment(
    *,
    user_id: str,
    target_date: str,
    event_start_time: str,
    event_end_time: str | None = None,
    duration_minutes: int | None = None,
    content: str,
    item_type: str | None = None,
    plan_id: int | None = None,
) -> ServiceResult:
    uid = str(user_id or "").strip()
    date = _date_text(target_date)
    title = norm_text(content)
    start_at = _calendar_datetime(date, event_start_time)
    if not uid or not date or not title or not start_at:
        return error_result("missing_required_field", "user_id, target_date, event_start_time, and content are required.")

    end_at = _calendar_datetime(date, event_end_time) if event_end_time else ""
    if not end_at and duration_minutes is not None:
        end_at = _add_minutes(start_at, max(to_int(duration_minutes, 0), 1))
    if not end_at:
        end_at = _add_minutes(start_at, 30)

    conflicts = _calendar_conflicts(user_id=uid, target_date=date, start_at=start_at, end_at=end_at, plan_id=plan_id)
    calendar_type = _resolve_calendar_type(item_type, title)
    if calendar_type not in VALID_CALENDAR_TYPES:
        return error_result("invalid_calendar_type", f"Unsupported calendar type: {calendar_type}")
    adjustments = _build_adjustments_for_event(conflicts=conflicts, event_end_time=end_at)
    proposal = {
        "action": "insert_event_and_adjust_calendar",
        "user_id": uid,
        "target_date": date,
        "insert_event": {
            "start_time": start_at,
            "end_time": end_at,
            "content": title,
            "type": calendar_type,
            "source": "用户输入",
            "is_milk_pump": calendar_type == CALENDAR_TYPE_PUMP,
        },
        "item": {
            "start_time": start_at,
            "end_time": end_at,
            "content": title,
            "type": calendar_type,
            "source": "用户输入",
            "is_milk_pump": calendar_type == CALENDAR_TYPE_PUMP,
        },
        "updates": adjustments,
        "conflicts": conflicts,
    }
    return ok_result(
        "calendar_adjustment_previewed",
        data={
            "proposal": proposal,
            "proposal_json": json.dumps(proposal, ensure_ascii=False),
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "insert_event": proposal["insert_event"],
            "updates": adjustments,
        },
    )


def apply_calendar_adjustment(
    *,
    user_id: str,
    target_date: str,
    proposal: Any,
    idempotency_key: str | None = None,
) -> ServiceResult:
    _ = idempotency_key
    uid = str(user_id or "").strip()
    date = _date_text(target_date)
    proposal_data = _parse_json_object(proposal)
    item = proposal_data.get("insert_event") if isinstance(proposal_data.get("insert_event"), dict) else {}
    if not item:
        item = proposal_data.get("item") if isinstance(proposal_data.get("item"), dict) else {}
    start_at = _calendar_datetime(date, item.get("start_time"))
    end_at = _calendar_datetime(date, item.get("end_time")) if item.get("end_time") else None
    content = norm_text(item.get("content"))
    item_type = _resolve_calendar_type(item.get("type"), content)
    if not uid or not date or not start_at or not content:
        return error_result("missing_required_field", "Confirmed calendar adjustment is missing required event fields.")
    if item_type not in VALID_CALENDAR_TYPES:
        return error_result("invalid_calendar_type", f"Unsupported calendar type: {item_type}")
    updates = proposal_data.get("updates") if isinstance(proposal_data.get("updates"), list) else []

    with transaction() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(task_id), 0) AS max_task_id FROM calendar WHERE user_id = ? AND date = ?",
            (uid, date),
        ).fetchone()
        task_id = int(row["max_task_id"] or 0) + 1
        cursor = conn.execute(
            """
            INSERT INTO calendar (
                user_id, plan_id, date, task_id, start_time, end_time,
                content, type, source, is_milk_pump, finish, created_at, modified_at
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, '用户输入', ?, 'false', CURRENT_TIMESTAMP, NULL)
            """,
            (uid, date, task_id, start_at, end_at, content, item_type, 1 if item_type == CALENDAR_TYPE_PUMP else 0),
        )
        inserted_id = int(cursor.lastrowid or 0)
        applied_updates: list[dict[str, Any]] = []
        for update in updates:
            if not isinstance(update, dict):
                continue
            item_id = to_int(update.get("item_id"), 0)
            new_start = _calendar_datetime(date, update.get("new_start_time"))
            new_end = _calendar_datetime(date, update.get("new_end_time")) if update.get("new_end_time") else None
            if item_id <= 0 or not new_start:
                continue
            cursor = conn.execute(
                """
                UPDATE calendar
                SET start_time = ?,
                    end_time = ?,
                    modified_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                  AND date = ?
                  AND item_id = ?
                """,
                (new_start, new_end, uid, date, item_id),
            )
            if int(cursor.rowcount or 0) > 0:
                applied_updates.append({"item_id": item_id, "new_start_time": new_start, "new_end_time": new_end})

    inserted = fetch_one(
        """
        SELECT item_id, user_id, plan_id, date, task_id, start_time, end_time,
               content, type, source, is_milk_pump, finish, created_at, modified_at
        FROM calendar
        WHERE item_id = ?
        """,
        (inserted_id,),
    )
    return ok_result(
        "calendar_adjustment_applied",
        data={
            "user_id": uid,
            "target_date": date,
            "inserted_event": _normalize_calendar_row(inserted or {}),
            "item": _normalize_calendar_row(inserted or {}),
            "applied_updates": applied_updates,
        },
    )


def update_calendar_item(
    *,
    user_id: str,
    item_id: int,
    start_time: str | None = None,
    end_time: str | None = None,
    content: str | None = None,
    item_type: str | None = None,
    finish: bool | None = None,
) -> ServiceResult:
    uid = str(user_id or "").strip()
    if not uid or not item_id:
        return error_result("missing_required_field", "user_id and item_id are required.")
    current = fetch_one(
        """
        SELECT item_id, user_id, date, start_time, end_time, content, type, is_milk_pump, finish
        FROM calendar
        WHERE user_id = ? AND item_id = ?
        """,
        (uid, int(item_id)),
    )
    if not current:
        return error_result("calendar_item_not_found", "Calendar item was not found.")
    item_date = str(current.get("date") or "")
    previous_finish = to_bool(current.get("finish"))

    fields: list[str] = []
    params: list[Any] = []
    if start_time is not None:
        normalized_start = _calendar_datetime(item_date, start_time)
        if not normalized_start:
            return error_result("invalid_datetime", "start_time must be a valid time or datetime.")
        fields.append("start_time = ?")
        params.append(normalized_start)
    if end_time is not None:
        normalized_end = _calendar_datetime(item_date, end_time)
        if not normalized_end:
            return error_result("invalid_datetime", "end_time must be a valid time or datetime.")
        fields.append("end_time = ?")
        params.append(normalized_end)
    if content is not None:
        fields.append("content = ?")
        params.append(str(content))
    if item_type is not None:
        if item_type not in VALID_CALENDAR_TYPES:
            return error_result("invalid_calendar_type", f"Unsupported calendar type: {item_type}")
        fields.append("type = ?")
        params.append(item_type)
    if finish is not None:
        fields.append("finish = ?")
        params.append("true" if finish else "false")
    if not fields:
        return error_result("empty_update", "No calendar item fields were provided.")

    fields.append("modified_at = CURRENT_TIMESTAMP")
    params.extend([uid, int(item_id)])
    execute(
        f"UPDATE calendar SET {', '.join(fields)} WHERE user_id = ? AND item_id = ?",
        params,
    )
    sync_result = {"pumping_id": 0, "feeding_id": 0}
    if finish is True and not previous_finish:
        sync_result = data_store.sync_completed_calendar_item_logs(user_id=uid, item_id=int(item_id))
    return ok_result("calendar_item_updated", data={"user_id": uid, "item_id": int(item_id), "synced_logs": sync_result})


def delete_calendar_item(*, user_id: str, item_id: int) -> ServiceResult:
    uid = str(user_id or "").strip()
    if not uid or not item_id:
        return error_result("missing_required_field", "user_id and item_id are required.")
    changed = execute("DELETE FROM calendar WHERE user_id = ? AND item_id = ?", [uid, int(item_id)])
    if changed <= 0:
        return error_result("calendar_item_not_found", "Calendar item was not found.")
    return ok_result("calendar_item_deleted", data={"user_id": uid, "item_id": int(item_id)})


def _normalize_calendar_row(row: dict[str, Any]) -> CalendarItem:
    item: CalendarItem = {
        "item_id": int(row.get("item_id") or 0),
        "user_id": str(row.get("user_id") or ""),
        "plan_id": row.get("plan_id"),
        "date": str(row.get("date") or ""),
        "task_id": row.get("task_id"),
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "content": row.get("content"),
        "type": row.get("type") or CALENDAR_TYPE_CUSTOM,
        "source": row.get("source") or "系统生成",
        "is_milk_pump": to_bool(row.get("is_milk_pump")),
        "finish": to_bool(row.get("finish")),
        "created_at": row.get("created_at"),
        "modified_at": row.get("modified_at"),
        "time": hhmm(row.get("start_time")),
        "time_point": hhmm(row.get("start_time")),
        }
    return item


def _calendar_conflicts(
    *,
    user_id: str,
    target_date: str,
    start_at: str,
    end_at: str,
    plan_id: int | None,
) -> list[CalendarItem]:
    rows = fetch_all(
        """
        SELECT item_id, user_id, plan_id, date, task_id, start_time, end_time,
               content, type, source, is_milk_pump, finish, created_at, modified_at
        FROM calendar
        WHERE user_id = ?
          AND date = ?
          AND (? IS NULL OR COALESCE(plan_id, 0) = COALESCE(?, 0))
          AND start_time < ?
          AND COALESCE(end_time, start_time) > ?
        ORDER BY start_time ASC, task_id ASC, item_id ASC
        """,
        (user_id, target_date, plan_id, plan_id, end_at, start_at),
    )
    return [_normalize_calendar_row(row) for row in rows]


def _build_adjustments_for_event(*, conflicts: list[CalendarItem], event_end_time: str) -> list[dict[str, Any]]:
    next_start = parse_datetime(event_end_time)
    if next_start is None:
        return []
    updates: list[dict[str, Any]] = []
    for item in conflicts:
        if not _is_milk_schedule_item(item):
            continue
        old_start = parse_datetime(item.get("start_time"))
        old_end = parse_datetime(item.get("end_time"))
        duration = int((old_end - old_start).total_seconds() / 60) if old_start is not None and old_end is not None else 15
        duration = max(duration, 1)
        new_start = next_start
        new_end = new_start + timedelta(minutes=duration)
        updates.append(
            {
                "item_id": item.get("item_id"),
                "task_id": item.get("task_id"),
                "content": item.get("content"),
                "type": item.get("type"),
                "old_start_time": item.get("start_time"),
                "old_end_time": item.get("end_time"),
                "new_start_time": _db_time(new_start),
                "new_end_time": _db_time(new_end),
            }
        )
        next_start = new_end
    return updates


def _resolve_calendar_type(item_type: Any, content: Any) -> str:
    token = norm_text(item_type)
    if token in VALID_CALENDAR_TYPES:
        return token
    text = norm_text(content).lower()
    if "亲喂" in text or "nursing" in text or "breastfeeding" in text:
        return CALENDAR_TYPE_NURSING
    if "吸奶" in text or "排奶" in text or "泵奶" in text or "pump" in text:
        return CALENDAR_TYPE_PUMP
    return CALENDAR_TYPE_CUSTOM


def _is_milk_schedule_item(item: CalendarItem) -> bool:
    item_type = item.get("type")
    return bool(item.get("is_milk_pump")) or item_type in {CALENDAR_TYPE_PUMP, CALENDAR_TYPE_NURSING}


def _calendar_datetime(target_date: str, value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return ""
    date = _date_text(target_date)
    if not date:
        return ""
    if _has_date(value):
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    return f"{date} {parsed.hour:02d}:{parsed.minute:02d}:00"


def _date_text(value: Any) -> str:
    parsed = parse_datetime(value)
    return parsed.date().isoformat() if parsed is not None else norm_text(value)[:10]


def _has_date(value: Any) -> bool:
    token = norm_text(value)
    return len(token) >= 10 and token[4:5] in {"-", "/"} and token[7:8] in {"-", "/"}


def _add_minutes(value: Any, minutes: int) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return ""
    return (parsed + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def _db_time(value: Any) -> str:
    parsed = parse_datetime(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}
