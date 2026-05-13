from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from ...config import load_project_env
from .. import data_store
from .feeding import estimate_breastfeeding_milk


SIMPLE_STATUS_ADVICE_PROMPT = """
你是 Momcozy 的泌乳和喂养状态建议助手。根据输入的生产日期、宝宝信息，以及近7天吸奶/亲喂/喂奶记录，生成简短自然语言建议。

要求：
- 只返回 JSON：{"lactation_advice":"...","feeding_advice":"..."}
- 每条 advice 必须是中文，50字以内。
- 语气亲和、鼓励，温柔，有朋友的感觉，千万不制造焦虑。
- 不诊断、不承诺奶量一定够或不够，不替代医生、儿科医生或 IBCLC。
- 有记录时，只基于记录做轻量总结和下一步建议。
- 记录少时，可以提醒建议仅供参考，并鼓励继续记录。
- 如果近7天没有任何吸奶、亲喂或喂奶记录：根据 delivery_date/postpartum_days 给通用建议，并温和提醒养成记录习惯。
""".strip()


def generate_status_advice(*, user_id: str, days: int = 7) -> dict[str, str] | None:
    """Generate both lactation and feeding advice for status creation."""

    uid = str(user_id or "").strip()
    if not uid:
        return None

    context = data_store.get_status_advice_context(user_id=uid, days=days)
    if not context:
        return None

    payload = _build_llm_payload(context)
    generated = _request_llm_status_advice(payload)
    if not generated:
        return None
    if not generated.get("lactation_advice", "").strip() or not generated.get("feeding_advice", "").strip():
        return None
    return generated


def _build_llm_payload(context: dict[str, Any]) -> dict[str, Any]:
    user_profile = context.get("user_profile") if isinstance(context.get("user_profile"), dict) else {}
    infant_profile = context.get("infant_profile") if isinstance(context.get("infant_profile"), dict) else {}
    pumping_records = context.get("pumping_records") if isinstance(context.get("pumping_records"), list) else []
    feeding_records = context.get("feeding_records") if isinstance(context.get("feeding_records"), list) else []

    return {
        "user_id": str(user_profile.get("user_id") or infant_profile.get("user_id") or ""),
        "delivery_date": str(user_profile.get("delivery_date") or infant_profile.get("birth_date") or ""),
        "postpartum_days": _days_since(user_profile.get("delivery_date") or infant_profile.get("birth_date")),
        "infant": {
            "infant_id": infant_profile.get("infant_id"),
            "birth_date": str(infant_profile.get("birth_date") or ""),
            "age_days": _days_since(infant_profile.get("birth_date")),
            "sex": str(infant_profile.get("sex") or ""),
        },
        "window": context.get("window") if isinstance(context.get("window"), dict) else {},
        "has_any_recent_record": bool(pumping_records or feeding_records),
        "pumping_summary": _summarize_pumping(
            pumping_records,
            user_id=str(user_profile.get("user_id") or infant_profile.get("user_id") or ""),
            as_of_time=(context.get("window") if isinstance(context.get("window"), dict) else {}).get("end_at"),
        ),
        "feeding_summary": _summarize_feeding(feeding_records),
    }


def _summarize_pumping(records: list[Any], *, user_id: str, as_of_time: Any = None) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    daily_totals: dict[str, float] = {}
    total_ml = 0.0
    breastfeeding_count = 0
    breastfeeding_estimate = estimate_breastfeeding_milk(user_id=user_id, as_of_time=as_of_time)

    for raw in records:
        if not isinstance(raw, dict):
            continue
        pump_type = _int(raw.get("pump_type"), 0)
        volume_ml = _float(raw.get("pump_milk_volum"))
        duration_minutes = _int_or_none(raw.get("pump_milk_duration"))
        if pump_type == 2:
            breastfeeding_count += 1
            effective_ml = breastfeeding_estimate or 0.0
        else:
            effective_ml = volume_ml
        if effective_ml <= 0 and (duration_minutes or 0) <= 0:
            continue

        time_text = str(raw.get("pump_start_time") or "")
        date_key = time_text[:10]
        total_ml += effective_ml
        if date_key:
            daily_totals[date_key] = daily_totals.get(date_key, 0.0) + effective_ml
        normalized.append(
            {
                "time": time_text,
                "pump_type": pump_type,
                "pump_source": _int(raw.get("pump_source"), 1),
                "volume_ml": round(volume_ml, 1),
                "duration_minutes": duration_minutes,
                "estimated_breastfeeding_ml": round(breastfeeding_estimate, 1) if breastfeeding_estimate is not None else None,
                "title": str(raw.get("pump_title") or ""),
            }
        )

    return {
        "has_records": bool(normalized),
        "record_count": len(normalized),
        "breastfeeding_count": breastfeeding_count,
        "total_effective_ml": round(total_ml, 1),
        "daily_totals": [{"date": key, "ml": round(value, 1)} for key, value in sorted(daily_totals.items())],
        "records": normalized[-30:],
    }


def _summarize_feeding(records: list[Any]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    daily_totals: dict[str, float] = {}
    bottle_or_formula_total = 0.0
    breastfeeding_count = 0
    formula_count = 0

    for raw in records:
        if not isinstance(raw, dict):
            continue
        feed_type = str(raw.get("feed_type") or "")
        amount = _float(raw.get("feed_milk_volum"))
        if amount <= 0:
            continue
        time_text = str(raw.get("feed_time") or "")
        date_key = time_text[:10]
        if feed_type == data_store.FEED_TYPE_CODE_TO_TEXT[0]:
            breastfeeding_count += 1
            amount_kind = "duration_minutes"
        else:
            amount_kind = "volume_ml"
            bottle_or_formula_total += amount
            if date_key:
                daily_totals[date_key] = daily_totals.get(date_key, 0.0) + amount
        if feed_type == data_store.FEED_TYPE_CODE_TO_TEXT[2]:
            formula_count += 1
        normalized.append(
            {
                "time": time_text,
                "feed_type": feed_type,
                "feed_action": _int(raw.get("feed_action"), 0),
                amount_kind: round(amount, 1),
                "title": str(raw.get("feeding_title") or ""),
            }
        )

    return {
        "has_records": bool(normalized),
        "record_count": len(normalized),
        "breastfeeding_count": breastfeeding_count,
        "formula_count": formula_count,
        "bottle_or_formula_total_ml": round(bottle_or_formula_total, 1),
        "daily_bottle_or_formula_totals": [{"date": key, "ml": round(value, 1)} for key, value in sorted(daily_totals.items())],
        "records": normalized[-30:],
    }


def _request_llm_status_advice(payload: dict[str, Any]) -> dict[str, str] | None:
    load_project_env()
    try:
        from openai import OpenAI
    except ImportError:
        return None

    try:
        client = OpenAI()
        response = client.responses.create(
            model=os.getenv("STATUS_ADVICE_MODEL", "gpt-5.4-mini"),
            instructions=SIMPLE_STATUS_ADVICE_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(payload, ensure_ascii=False),
                        }
                    ],
                }
            ],
            reasoning={"effort": "low"},
            text={"format": {"type": "text"}, "verbosity": "low"},
            store=False,
            prompt_cache_key="momcozy-status-advice-v1",
        )
    except Exception:
        return None

    return _parse_advice_response(response)


def _parse_advice_response(response: object) -> dict[str, str] | None:
    text = _response_text(response)
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    lactation_advice = _clean_advice(parsed.get("lactation_advice"))
    feeding_advice = _clean_advice(parsed.get("feeding_advice"))
    if not lactation_advice and not feeding_advice:
        return None
    return {
        "lactation_advice": lactation_advice,
        "feeding_advice": feeding_advice,
    }


def _clean_advice(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text[:50]


def _response_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    output = response.get("output", []) if isinstance(response, dict) else getattr(response, "output", [])
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        item_type = _item_value(item, "type")
        if item_type == "message":
            content = _item_value(item, "content") or []
            if not isinstance(content, list):
                continue
            for content_item in content:
                if _item_value(content_item, "type") in {"output_text", "text"}:
                    text = _item_value(content_item, "text")
                    if isinstance(text, str):
                        parts.append(text)
        elif item_type == "output_text":
            text = _item_value(item, "text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def _item_value(item: object, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _days_since(date_text: Any) -> int | None:
    token = str(date_text or "").strip()
    if not token:
        return None
    try:
        parsed = datetime.fromisoformat(token).date()
    except Exception:
        return None
    return max(0, (datetime.now().date() - parsed).days)


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(value))
    except Exception:
        return None
