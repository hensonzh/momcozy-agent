from __future__ import annotations

import json
import re
from typing import Any

from ..types import RuntimeInputs

HOSPITAL_BAG_CART_URL = "/hospital-bag-cart"
HOSPITAL_BAG_CART_LINK = f"[打开待产包一键打包下单页]({HOSPITAL_BAG_CART_URL})"
PUMP_ITEM = {
    "label": "便携式吸奶器",
    "quantity": "1台",
    "priority": "recommended",
    "note": "如果计划母乳或混合喂养，可作为初期涨奶或追奶的备用选择；具体使用以医院和哺乳顾问建议为准。",
}
HOSPITAL_BAG_CART_ASSISTANT_FOLLOWUP = {
    "kind": "hospital_bag_cart",
    "message": (
        "我也把清单里适合直接购买的妈妈/宝宝母婴用品打包成了一个购物车，"
        "证件、医院确认项和医疗相关内容不会放进去。\n\n"
        f"**{HOSPITAL_BAG_CART_LINK}**\n\n"
        "下单前记得删掉医院已提供、家里已有或医生不建议准备的物品。"
    ),
}
BIRTH_PLAN_DISCLAIMER = (
    "这张卡只用于沟通。请优先遵循医生和医院建议，尤其是因安全原因需要调整计划时。"
)
BIRTH_PLAN_ASSISTANT_FOLLOWUP = {
    "kind": "birth_plan_card_guidance",
    "message": "你可以提前和医院确认，并在产检或入院前把这张卡给医生/护士看，用它快速沟通你的重点偏好和需要讨论的问题。",
}
REMOVED_HOSPITAL_BAG_FORM_FIELD_IDS = {
    "hospital_rules_or_notes",
    "existing_checklist_or_photo_note",
}
PLACEHOLDER_VALUES = {"", "to confirm", "待确认", "未确定", "不确定", "none", "n/a"}
BIRTH_PATH_ALIASES = {
    "vaginal": "顺产",
    "natural": "顺产",
    "顺产": "顺产",
    "planned_c_section": "刨腹产",
    "c_section": "刨腹产",
    "c-section": "刨腹产",
    "cesarean": "刨腹产",
    "剖宫产": "刨腹产",
    "计划剖宫产": "刨腹产",
    "剖腹产": "刨腹产",
    "刨腹产": "刨腹产",
}


def create_form(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    form_id = str(args.get("form_id", "form"))
    fields = _normalize_form_fields(args.get("fields", []))
    description = str(args.get("description", ""))
    if form_id == "hospital_bag_intake":
        fields = [field for field in fields if field.get("id") not in REMOVED_HOSPITAL_BAG_FORM_FIELD_IDS]
        description = ""
    return {
        "tool_name": "ui_form_create",
        "status": "form_created",
        "form": {
            "id": form_id,
            "title": args.get("title", ""),
            "description": description,
            "submit_label": args.get("submit_label", "确认"),
            "fields": fields,
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
    title = str(card_json.get("title") or "").strip()
    if not title or title in {"待产包卡片", "Hospital Bag Card"}:
        card_json["title"] = "待产包"
    elif "待产包卡片" in title:
        card_json["title"] = title.replace("待产包卡片", "待产包")

    groups = card_json.get("packing_groups")
    if not isinstance(groups, list):
        groups = []
        card_json["packing_groups"] = groups

    if _formula_only_feeding_intention(inputs):
        return dict(HOSPITAL_BAG_CART_ASSISTANT_FOLLOWUP)

    group = _find_lactation_or_postpartum_group(groups)
    if group is None:
        group = {"group_id": "postpartum", "title": "妈妈产后护理与哺乳用品", "items": []}
        insert_at = 1 if groups else 0
        groups.insert(insert_at, group)

    items = group.get("items")
    if not isinstance(items, list):
        items = []
        group["items"] = items

    _ensure_breast_pump_visible(items)

    return dict(HOSPITAL_BAG_CART_ASSISTANT_FOLLOWUP)


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
        "title": _localized_birth_plan_title(_first_text(source.get("title"))) or "分娩沟通卡",
        "subtitle": _localized_birth_plan_subtitle(_first_text(source.get("subtitle"))) or "产房沟通优先级卡片",
        "overview": {
            "due_date_or_week": _first_text(
                overview.get("due_date_or_week"),
                owner.get("due_date_or_week"),
                form_data.get("due_date_or_week"),
            )
            or "待确认",
            "birth_path": _normalize_birth_path(
                _first_text(
                    overview.get("birth_path"),
                    birth_preferences.get("birth_path"),
                    form_data.get("birth_path"),
                )
            )
            or "待确认",
            "birth_setting": _first_text(
                overview.get("birth_setting"),
                owner.get("birth_setting"),
                form_data.get("birth_setting"),
            ),
            "support_people": _first_text(
                overview.get("support_people"),
                owner.get("support_people"),
                form_data.get("support_people"),
            )
            or "待确认",
        },
        "personalized_notes": _birth_plan_personalized_notes(form_data),
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
        "questions_for_hospital": _normalize_birth_plan_items(
            source.get("questions_for_hospital"),
            _birth_plan_default_questions(form_data),
            max_items=3,
        ),
        "medical_notes": _normalize_medical_notes(form_data.get("medical_notes")),
        "disclaimer": _localized_disclaimer(_first_text(source.get("disclaimer"))) or BIRTH_PLAN_DISCLAIMER,
    }

    card_json.clear()
    card_json.update(compact)
    return dict(BIRTH_PLAN_ASSISTANT_FOLLOWUP)


def _find_lactation_or_postpartum_group(groups: list[Any]) -> dict[str, Any] | None:
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("group_id", "")).lower()
        title = str(group.get("title", "")).lower()
        if any(token in group_id for token in ("lactation", "breastfeeding", "feeding", "postpartum", "mom", "mother")):
            return group
        if any(token in title for token in ("lactation", "breastfeeding", "feeding", "postpartum", "mom", "mother", "哺乳", "喂养", "妈妈", "产后")):
            return group
    return None


def _ensure_breast_pump_visible(items: list[Any]) -> None:
    pump_index = _breast_pump_item_index(items)
    target_index = min(2, len(items))
    if pump_index is None:
        items.insert(target_index, dict(PUMP_ITEM))


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


def _localized_birth_plan_title(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"birth plan card", "labor room communication priority card"}:
        return "分娩沟通卡"
    return value


def _localized_birth_plan_subtitle(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"birth plan card", "labor room communication priority card"}:
        return "产房沟通优先级卡片"
    return value


def _normalize_birth_path(value: str) -> str:
    text = value.strip()
    if not _has_meaningful_value(text):
        return ""
    return BIRTH_PATH_ALIASES.get(text.lower()) or BIRTH_PATH_ALIASES.get(text) or text


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
            softened = _soften_birth_plan_request(_normalize_birth_plan_text(item))
            if softened and softened not in items:
                items.append(softened)
            if len(items) >= max_items:
                return items
    return items


def _normalize_medical_notes(value: Any) -> list[str]:
    # Medical notes must remain user-supplied facts only; do not derive them from model-generated card fields.
    return _flatten_text_items(value)[:3]


def _birth_plan_personalized_notes(form_data: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    due = _first_text(form_data.get("due_date_or_week"))
    birth_path = _normalize_birth_path(_first_text(form_data.get("birth_path")))
    birth_setting = _first_text(form_data.get("birth_setting"))
    support_people = _first_text(form_data.get("support_people"))
    if due or birth_path:
        parts = [part for part in (due, birth_path) if part]
        notes.append(f"基于{'、'.join(parts)}，整理成适合产检或入院沟通的重点卡片。")
    if support_people:
        notes.append(f"已把{support_people}作为重要沟通参与人。")
    if birth_setting:
        notes.append(f"可在{birth_setting}产检或入院前给医护团队查看。")
    return notes[:3]


def _birth_plan_default_questions(form_data: dict[str, Any]) -> list[str]:
    questions = [
        "分娩沟通卡：确认是否可以在产检或入院时交给医生/护士参考。",
        "陪产/支持人：确认谁可以参与沟通、陪产或术前/产房决策。",
    ]
    if _normalize_birth_path(_first_text(form_data.get("birth_path"))) == "刨腹产":
        questions.append("术后接触宝宝/喂养：确认安全允许时的肌肤接触、喂养和宝宝护理流程。")
    else:
        questions.append("疼痛管理：确认无痛/麻醉沟通时机和可选方案。")
    return questions


def _normalize_birth_plan_text(text: str) -> str:
    normalized = re.sub(r"^\s*\d+[.)、．]\s*", "", text.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    lowered = normalized.lower()
    if lowered in {"skin-to-skin", "skin to skin"}:
        return "出生后尽早肌肤接触"
    return normalized.replace("skin-to-skin", "出生后尽早肌肤接触").replace("skin to skin", "出生后尽早肌肤接触")


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
