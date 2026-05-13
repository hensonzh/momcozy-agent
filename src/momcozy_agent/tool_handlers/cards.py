from __future__ import annotations

import json
from typing import Any

from ..types import RuntimeInputs

PUMP_PRODUCT_URL = (
    "https://sea.momcozy.com/collections/weekly-deals/products/"
    "momcozy-mobile-style-hands-free-breast-pump?variant=46306441625789"
)
PUMP_PRODUCT_LINK = f"[sea.momcozy.com]({PUMP_PRODUCT_URL})"
PUMP_ITEM = {
    "label": "便携式吸奶器",
    "priority": "recommended",
    "note": "如果计划母乳或混合喂养，可作为初期涨奶或追奶的备用选择；具体使用以医院和哺乳顾问建议为准。",
}
PUMP_ASSISTANT_FOLLOWUP = {
    "kind": "optional_product_resource",
    "message": (
        "如果你还没有准备吸奶器，可以把它当作可选备用项先了解一下："
        f"{PUMP_PRODUCT_LINK}。不一定现在购买，是否带去医院仍以医院和哺乳顾问建议为准。"
    ),
}
BIRTH_PLAN_DISCLAIMER = (
    "这张卡只用于沟通。请优先遵循医生和医院建议，尤其是因安全原因需要调整计划时。"
)
BIRTH_PLAN_ASSISTANT_FOLLOWUP = {
    "kind": "birth_plan_card_guidance",
    "message": "你可以在产检或入院前把这张卡给医生/护士看；其中问题部分建议提前和医院确认。",
}
PLACEHOLDER_VALUES = {"", "to confirm", "待确认", "未确定", "不确定", "none", "n/a"}


def create_form(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    return {
        "tool_name": "ui_form_create",
        "status": "form_created",
        "form": {
            "id": args.get("form_id", "form"),
            "title": args.get("title", ""),
            "description": args.get("description", ""),
            "submit_label": args.get("submit_label", "确认"),
            "fields": _normalize_form_fields(args.get("fields", [])),
        },
    }


def create_card(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    card_json = args.get("card_json", {})
    if not isinstance(card_json, dict):
        card_json = {}
    card_type = args.get("card_type", "")
    assistant_followup = None
    if card_type == "hospital_bag_card":
        assistant_followup = _prepare_hospital_bag_card(card_json, inputs)
    elif card_type == "birth_plan_card":
        assistant_followup = _prepare_birth_plan_card(card_json, inputs)

    result = {
        "tool_name": "ui_card_create",
        "status": "card_created",
        "card": {
            "card_type": card_type,
            "schema_version": args.get("schema_version", ""),
            "card_json": card_json,
        },
    }
    if assistant_followup:
        result["assistant_followup"] = assistant_followup
    return result


def _prepare_hospital_bag_card(card_json: dict[str, Any], inputs: RuntimeInputs) -> dict[str, str] | None:
    if _formula_only_feeding_intention(inputs):
        return None

    groups = card_json.get("packing_groups")
    if not isinstance(groups, list):
        groups = []
        card_json["packing_groups"] = groups

    group = _find_postpartum_group(groups)
    if group is None:
        group = {"group_id": "postpartum", "title": "妈妈入院基础包", "items": []}
        insert_at = 1 if groups else 0
        groups.insert(insert_at, group)
    else:
        _move_group_into_visible_range(groups, group)

    items = group.get("items")
    if not isinstance(items, list):
        items = []
        group["items"] = items

    _ensure_breast_pump_visible(items)

    return dict(PUMP_ASSISTANT_FOLLOWUP)


def _prepare_birth_plan_card(card_json: dict[str, Any], inputs: RuntimeInputs) -> dict[str, str]:
    source = dict(card_json)
    form_data = _confirmed_form_data(inputs)
    owner = _dict_value(source.get("owner"))
    overview = _dict_value(source.get("overview"))
    birth_preferences = _dict_value(source.get("birth_preferences"))
    plan_change_values = _birth_plan_change_values(source.get("if_plans_change"))

    compact = {
        "card_type": "birth_plan_card",
        "schema_version": "1.0",
        "title": _first_text(source.get("title")) or "分娩沟通卡",
        "subtitle": _first_text(source.get("subtitle")) or "产房沟通优先级卡片",
        "overview": {
            "due_date_or_week": _first_text(
                overview.get("due_date_or_week"),
                owner.get("due_date_or_week"),
                form_data.get("due_date_or_week"),
            )
            or "待确认",
            "birth_path": _first_text(
                overview.get("birth_path"),
                birth_preferences.get("birth_path"),
                form_data.get("birth_path"),
            )
            or "待确认",
            "support_people": _first_text(
                overview.get("support_people"),
                owner.get("support_people"),
                form_data.get("support_people"),
            )
            or "待确认",
        },
        "top_priorities": _normalize_birth_plan_items(
            source.get("top_priorities"),
            _nested_text(source, "if_plans_change", "what_matters_most"),
            form_data.get("top_priorities"),
            max_items=3,
        ),
        "communication": _normalize_birth_plan_items(
            source.get("communication"),
            source.get("communication_preferences"),
            form_data.get("communication_preferences"),
            max_items=3,
        ),
        "pain_relief": _normalize_birth_plan_items(
            source.get("pain_relief"),
            source.get("pain_relief_preferences"),
            form_data.get("pain_relief_preferences"),
            max_items=3,
        ),
        "baby_after_birth": _normalize_birth_plan_items(
            source.get("baby_after_birth"),
            source.get("baby_after_birth_preferences"),
            form_data.get("baby_after_birth_preferences"),
            max_items=3,
        ),
        "if_plans_change": _normalize_birth_plan_items(
            *plan_change_values,
            form_data.get("if_plans_change"),
            max_items=3,
        ),
        "questions_for_hospital": _normalize_birth_plan_items(source.get("questions_for_hospital"), max_items=3),
        "medical_notes": _normalize_medical_notes(form_data.get("medical_notes")),
        "disclaimer": _localized_disclaimer(_first_text(source.get("disclaimer"))) or BIRTH_PLAN_DISCLAIMER,
    }

    card_json.clear()
    card_json.update(compact)
    return dict(BIRTH_PLAN_ASSISTANT_FOLLOWUP)


def _find_postpartum_group(groups: list[Any]) -> dict[str, Any] | None:
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("group_id", "")).lower()
        title = str(group.get("title", "")).lower()
        if any(token in group_id for token in ("postpartum", "mom", "mother")):
            return group
        if any(token in title for token in ("postpartum", "mom", "mother", "妈妈", "产后")):
            return group
    return None


def _move_group_into_visible_range(groups: list[Any], group: dict[str, Any]) -> None:
    try:
        index = groups.index(group)
    except ValueError:
        return
    if index < 3:
        return
    groups.pop(index)
    groups.insert(1 if groups else 0, group)


def _has_breast_pump_item(items: list[Any]) -> bool:
    return _breast_pump_item_index(items) is not None


def _ensure_breast_pump_visible(items: list[Any]) -> None:
    pump_index = _breast_pump_item_index(items)
    target_index = min(2, len(items))
    if pump_index is None:
        items.insert(target_index, dict(PUMP_ITEM))
        return
    if pump_index < 4:
        return
    pump_item = items.pop(pump_index)
    items.insert(min(target_index, len(items)), pump_item)


def _breast_pump_item_index(items: list[Any]) -> int | None:
    for index, item in enumerate(items):
        text = json.dumps(item, ensure_ascii=False).lower() if isinstance(item, dict) else str(item).lower()
        if "吸奶" in text or "breast pump" in text or "pump" in text:
            return index
    return None


def _formula_only_feeding_intention(inputs: RuntimeInputs) -> bool:
    data = _confirmed_form_data(inputs)
    if data:
        feeding_intention = str(data.get("feeding_intention", "")).strip().lower()
        return feeding_intention in {"配方", "formula", "formula feeding"}
    message = str(inputs.get("user_message", ""))
    marker = "confirmed_form_data:"
    if marker not in message:
        return False
    raw_json = message.split(marker, 1)[1].strip()
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return False
    feeding_intention = str(data.get("feeding_intention", "")).strip().lower()
    return feeding_intention in {"配方", "formula", "formula feeding"}


def _confirmed_form_data(inputs: RuntimeInputs) -> dict[str, Any]:
    message = str(inputs.get("user_message", ""))
    marker = "confirmed_form_data:"
    if marker not in message:
        return {}
    raw_json = message.split(marker, 1)[1].strip()
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            text = ", ".join(str(item) for item in value if _has_meaningful_value(item))
        elif isinstance(value, dict):
            text = ", ".join(
                str(nested_value)
                for nested_value in value.values()
                if _has_meaningful_value(nested_value)
            )
        else:
            text = str(value or "").strip()
        if _has_meaningful_value(text):
            return text
    return ""


def _localized_disclaimer(value: str) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    if "this card is for communication only" in normalized or "clinician and hospital guidance" in normalized:
        return BIRTH_PLAN_DISCLAIMER
    return value


def _nested_text(source: dict[str, Any], *keys: str) -> str:
    current: Any = source
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return _first_text(current)


def _birth_plan_change_values(value: Any) -> list[Any]:
    if not isinstance(value, dict):
        return [value]
    return [value.get("how_to_explain_changes"), value.get("who_should_be_involved")]


def _normalize_birth_plan_items(*values: Any, max_items: int) -> list[str]:
    items: list[str] = []
    for value in values:
        for item in _flatten_text_items(value):
            softened = _soften_birth_plan_request(item)
            if softened and softened not in items:
                items.append(softened)
            if len(items) >= max_items:
                return items
    return items


def _normalize_medical_notes(value: Any) -> list[str]:
    # Medical notes must remain user-supplied facts only; do not derive them from model-generated card fields.
    return _flatten_text_items(value)[:3]


def _flatten_text_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_flatten_text_items(item))
        return items
    if isinstance(value, dict):
        items = []
        for item in value.values():
            items.extend(_flatten_text_items(item))
        return items
    text = str(value).strip()
    if not _has_meaningful_value(text):
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for token in ("；", ";", "\n"):
        normalized = normalized.replace(token, "\n")
    items = []
    for raw_item in normalized.split("\n"):
        item = raw_item.strip(" -•、，,。.")
        if _has_meaningful_value(item):
            items.append(item)
    return items


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_value(item) for item in value)
    text = str(value).strip()
    return text.lower() not in PLACEHOLDER_VALUES


def _soften_birth_plan_request(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    english_tokens = ("i refuse", "must", "never", "do not", "don't")
    chinese_tokens = ("拒绝", "不要", "不允许", "必须", "一定要")
    strong_tokens = (*english_tokens, *chinese_tokens)
    if not any(token in lowered or token in stripped for token in strong_tokens):
        return stripped

    softened = stripped
    for token in strong_tokens:
        softened = softened.replace(token, "").replace(token.capitalize(), "")
    softened = softened.strip(" ，,。.:：;；")
    if not softened:
        softened = "这项偏好"
    return f"在{softened}前，请先和我沟通。"


def _normalize_form_fields(raw_fields: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_fields, list):
        return []

    fields: list[dict[str, Any]] = []
    for raw_field in raw_fields:
        field = raw_field
        if isinstance(raw_field, str):
            try:
                parsed = json.loads(raw_field)
            except json.JSONDecodeError:
                continue
            field = parsed
        if not isinstance(field, dict):
            continue

        normalized = {
            "id": str(field.get("id", "")),
            "label": str(field.get("label", "")),
            "type": str(field.get("type", "text")),
            "required": bool(field.get("required", False)),
        }
        for optional_key in ("help_text", "placeholder", "default_value"):
            value = field.get(optional_key)
            if value is not None and value != "":
                normalized[optional_key] = value
        options = field.get("options")
        if isinstance(options, list) and options:
            normalized["options"] = [str(option) for option in options]
        if normalized["id"] and normalized["label"]:
            fields.append(normalized)

    return fields
