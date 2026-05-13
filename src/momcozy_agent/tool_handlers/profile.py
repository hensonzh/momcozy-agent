from __future__ import annotations

from typing import Any

from ..types import RuntimeInputs


def get_profile(args: dict[str, Any], inputs: RuntimeInputs) -> dict[str, Any]:
    return {
        "tool_name": "profile_get",
        "user_profile": inputs.get("user_profile", {}),
        "baby_profile": inputs.get("baby_profile", {}),
        "service_state": inputs.get("service_state", {}),
        "status": "read_from_runtime_inputs",
    }

