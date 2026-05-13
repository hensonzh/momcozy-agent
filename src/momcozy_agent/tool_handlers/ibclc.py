from __future__ import annotations

from typing import Any

from ..types import RuntimeInputs

DEFAULT_CHAT_URL = "/ibclc-chat.html"


def create_ibclc_consult_card(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    consultant = {
        "name": _text(args.get("consultant_name"), "Emily Chen"),
        "bio": _text(
            args.get("consultant_bio"),
            "国际认证哺乳顾问，专注产后亲喂、吸奶计划、乳头疼痛、堵奶和奶量管理支持。",
        ),
    }
    card = {
        "card_type": "ibclc_consult_card",
        "schema_version": "1.0",
        "consultant": consultant,
        "chat": {
            "url": _text(args.get("chat_url"), DEFAULT_CHAT_URL),
        },
    }
    return {
        "tool_name": "ibclc_consult_card_create",
        "status": "ibclc_consult_card_created",
        "card": card,
    }


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback
