from __future__ import annotations

from typing import Any

from .types import FunctionToolDefinition, ToolName

USER_ID = {"type": "string", "description": "应用侧用户 ID。"}
BABY_ID = {"type": "string", "description": "已知时填写宝宝档案 ID。"}
ISO_DATE = {"type": "string", "description": "ISO-8601 日期或日期时间。"}

# JSON_OBJECT_STRING is intentionally a string-typed field, used only for
# free-form structured payloads where defining a complete nested schema is
# impractical (for example arbitrary record events, profile patches, or
# rendered service card JSON). Application-side executors decode the string
# back into a dict before use.
JSON_OBJECT_STRING = {
    "type": "string",
    "description": '以字符串编码的自由 JSON 对象。不需要字段时使用 "{}"。',
}


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize a JSON schema for OpenAI strict-mode function tools."""

    types = _schema_types(schema)

    if "object" in types:
        schema.setdefault("additionalProperties", False)
        schema["required"] = list(schema.get("properties", {}).keys())
        for property_schema in schema.get("properties", {}).values():
            if isinstance(property_schema, dict):
                _strict_schema(property_schema)

    if "array" in types:
        items = schema.get("items")
        if isinstance(items, dict):
            _strict_schema(items)

    return schema


def _schema_types(schema: dict[str, Any]) -> set[str]:
    type_value = schema.get("type")
    if isinstance(type_value, str):
        return {type_value}
    if isinstance(type_value, list):
        return {item for item in type_value if isinstance(item, str)}
    return set()


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """Mark a property schema as nullable for strict-mode function tools."""

    cloned = dict(schema)
    type_value = cloned.get("type")
    if isinstance(type_value, str):
        if type_value != "null":
            cloned["type"] = [type_value, "null"]
    elif isinstance(type_value, list):
        if "null" not in type_value:
            cloned["type"] = [*type_value, "null"]
    else:
        cloned["type"] = ["null"]
    return cloned


def _function_tool(
    name: ToolName,
    description: str,
    properties: dict[str, Any],
) -> FunctionToolDefinition:
    parameters = _strict_schema(
        {
            "type": "object",
            "properties": properties,
        }
    )

    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": parameters,
    }


FORM_FIELD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "应用表单层使用的稳定字段 ID。"},
        "label": {"type": "string", "description": "展示给用户看的字段标签。"},
        "type": {
            "type": "string",
            "description": "字段输入类型，例如 text、textarea、select、multi_select、checkbox_group、radio、checkbox、date 或 number。",
        },
        "required": {"type": "boolean"},
        "help_text": _nullable({"type": "string"}),
        "placeholder": _nullable({"type": "string"}),
        "default_value": _nullable({"type": "string"}),
        "options": _nullable(
            {
                "type": "array",
                "items": {"type": "string"},
                "description": "select、multi_select、checkbox_group、radio 或 checkbox 字段允许的字符串选项。",
            }
        ),
    },
}


FUNCTION_TOOLS: dict[ToolName, FunctionToolDefinition] = {
    "list_skills": _function_tool(
        "list_skills",
        "列出可用的结构化服务 skill，包括名称、描述、触发条件、服务范围和安全边界。无副作用。只在判断是否需要结构化服务流程时使用；问候或普通问答不要使用。",
        {},
    ),
    "load_skill": _function_tool(
        "load_skill",
        "加载某个结构化服务 skill 的完整 SKILL.md，以及可用 references、scripts 和 assets 列表。无副作用。当用户需要该流程时使用，例如卡片、个性化计划、转接准备、基于记录的分析或设备专项支持；问候或普通科普回答不要使用。",
        {"skill_id": {"type": "string", "enum": ["birth-prep", "milk-management", "emotion-support", "device-guidance"]}},
    ),
    "search_skill_assets": _function_tool(
        "search_skill_assets",
        "在已加载 skill 的可用 reference、script 和 asset 文件名中搜索。无副作用。不会暴露任意文件系统访问。",
        {"skill_id": {"type": "string"}, "query": {"type": "string"}},
    ),
    "read_skill_file": _function_tool(
        "read_skill_file",
        "读取已加载 skill 目录下被允许的文本 reference 或 asset 文件。无副作用。只能读取 load_skill 或 search_skill_assets 返回的路径；脚本应使用 run_approved_skill_script。",
        {
            "skill_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["references", "assets"]},
            "path": {"type": "string"},
        },
    ),
    "run_approved_skill_script": _function_tool(
        "run_approved_skill_script",
        "请求执行已加载 skill 中被批准的脚本。必须由应用侧审批并执行；模型永远不能获得 shell 访问。",
        {
            "skill_id": {"type": "string"},
            "script_name": {"type": "string"},
            "args": _nullable(JSON_OBJECT_STRING),
        },
    ),
    "ui_form_create": _function_tool(
        "ui_form_create",
        "创建前端可渲染的表单规格，用于在生成服务卡片前收集或确认用户信息。无后端副作用。用于生成分娩沟通卡或待产包卡片前的产前服务表单。",
        {
            "form_id": {"type": "string", "description": "稳定表单 ID，例如 birth_plan_card_intake 或 hospital_bag_intake。"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "submit_label": {"type": "string"},
            "fields": {
                "type": "array",
                "items": FORM_FIELD_SCHEMA,
                "description": "由前端渲染的表单字段。不适用 help_text、placeholder、default_value 或 options 时使用 null。",
            },
        },
    ),
    "ui_card_create": _function_tool(
        "ui_card_create",
        "创建前端可渲染的结构化服务卡片产物。无后端副作用。在 confirmed_form_data 可用且服务卡片 JSON 已生成后使用。",
        {
            "card_type": {"type": "string", "enum": ["birth_plan_card", "hospital_bag_card"]},
            "schema_version": {"type": "string"},
            "card_json": JSON_OBJECT_STRING,
        },
    ),
    "ibclc_consult_card_create": _function_tool(
        "ibclc_consult_card_create",
        "创建前端可渲染的 IBCLC 在线咨询卡片，无后端副作用。仅在用户明确要求或确认需要 IBCLC/哺乳顾问/真人或人工哺乳咨询/在线咨询时使用。若是智能体自主判断需要持证哺乳顾问介入，应先简短说明原因并询问用户是否需要在线咨询 IBCLC；用户同意后再调用本工具。不要因为用户首次提到疼痛、堵奶、奶量担忧或宝宝摄入风险就直接触发。前端只渲染顾问姓名、顾问简介和在线咨询跳转地址。",
        {
            "consultant_name": _nullable({"type": "string", "description": "前端名片展示的 IBCLC 顾问姓名；不确定时传 null，由工具使用默认 demo 顾问。"}),
            "consultant_bio": _nullable({"type": "string", "description": "前端名片展示的顾问简介；不确定时传 null，由工具使用默认简介。"}),
            "chat_url": _nullable({"type": "string", "description": "在线咨询按钮跳转的 H5 URL；不确定时传 null，由工具使用默认页面。"}),
        },
    ),
    "profile_get": _function_tool(
        "profile_get",
        "读取用户和宝宝档案摘要。无副作用。",
        {"user_id": USER_ID},
    ),
    "handoff_summary_generate": _function_tool(
        "handoff_summary_generate",
        "生成简洁的专业转接摘要。无副作用。",
        {"user_id": USER_ID, "issue_type": {"type": "string"}, "facts": JSON_OBJECT_STRING},
    ),
    "device_manual_search": _function_tool(
        "device_manual_search",
        "补充 Momcozy 吸奶器设备资料。无副作用。用于获取当前型号说明书、检索 FAQ 问答、查找步骤图片。用户问部件是什么、作用原理、为什么、能不能、多少、区别、是否正常等日常设备知识时，应使用 topic=faq 检索 FAQ。已获得同型号 manual 后，连续步骤应复用已有内容；只有新的 FAQ 问题或缺少步骤图片时才再次调用。",
        {
            "model": {"type": "string", "enum": ["Air1", "unknown"], "description": "已确认的设备型号。当前只支持 Air1；未知型号必须传 unknown。"},
            "query": {"type": "string", "description": "用户的设备问题，或需要检索的具体指导主题。"},
            "topic": {
                "type": "string",
                "enum": ["overview", "unboxing", "setup", "daily_use", "cleaning", "disinfection", "assembly", "flange", "suction", "charging", "bluetooth", "milk_storage", "troubleshooting", "parts", "faq", "other"],
            },
            "max_results": {"type": "number", "description": "希望返回的 FAQ 片段数量，通常为 2 到 4。首次加载会按型号返回完整说明书；已加载时可能只返回轻量状态、FAQ 和相关图片。"},
        },
    ),
    "support_ticket_draft_create": _function_tool(
        "support_ticket_draft_create",
        "为未解决的 Momcozy 吸奶器或设备售后问题创建前端可确认的客服工单草稿。不会对外提交。用于排查未解决、用户明显沮丧、请求客服/退货/保修、反馈缺件或疑似缺陷，或设备安全问题需要升级支持时。",
        {
            "issue_type": {
                "type": "string",
                "enum": ["malfunction", "missing_parts", "defect", "warranty", "return_or_refund", "order_or_shipping", "usage_help", "safety_concern", "other"],
            },
            "issue_summary": {"type": "string", "description": "面向客服和用户的简洁问题摘要，用于预填工单。"},
            "product_model": _nullable({"type": "string"}),
            "order_number": _nullable({"type": "string"}),
            "purchase_channel": _nullable({"type": "string"}),
            "user_contact": _nullable({"type": "string"}),
            "troubleshooting_done": _nullable({"type": "array", "items": {"type": "string"}}),
            "urgency": {"type": "string", "enum": ["normal", "high", "safety"]},
            "user_emotion": _nullable({"type": "string", "description": "简短描述观察到的用户情绪，例如沮丧、焦虑或生气。"}),
            "attachments_note": _nullable({"type": "string", "description": "说明已提供或仍需要的相关图片/视频附件。"}),
        },
    ),
}
