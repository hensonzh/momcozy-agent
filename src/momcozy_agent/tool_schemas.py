from __future__ import annotations

from typing import Any

from .types import FunctionToolDefinition, ToolName

# JSON_OBJECT_STRING is intentionally a string-typed field, used only for
# free-form structured payloads where defining a complete nested schema is
# impractical (for example arbitrary record events, profile patches, or
# rendered service card JSON). Application-side executors decode the string
# back into a dict before use.
JSON_OBJECT_STRING = {
    "type": "string",
    "description": '以字符串编码的自由 JSON 对象。不需要字段时使用 "{}"。',
}
ISO_DATE = {"type": "string", "description": "ISO-8601 日期，例如 2026-05-07。"}


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
    enum_values = cloned.get("enum")
    if isinstance(enum_values, list) and None not in enum_values:
        cloned["enum"] = [*enum_values, None]
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
        "读取客户端当前会话传入的用户、宝宝和服务状态摘要。无副作用。不需要模型提供用户 ID。",
        {},
    ),
    "handoff_summary_generate": _function_tool(
        "handoff_summary_generate",
        "生成简洁的专业转接摘要。无副作用。",
        {"issue_type": {"type": "string"}, "facts": JSON_OBJECT_STRING},
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
    "milk_context_get": _function_tool(
        "milk_context_get",
        "GET 只读工具：读取当前用户的奶量管理上下文，包括用户/宝宝资料和最新计划元数据。只返回结构化事实；最终解释由模型完成。user_id 由应用运行时注入，模型不要提供。",
        {},
    ),
    "milk_assessment_evaluate": _function_tool(
        "milk_assessment_evaluate",
        "EVALUATE 只读工具：基于固定参考数据和记录聚合，返回近期奶量状态、缺失数据和规则命中。不是诊断，也不生成最终用户话术。",
        {
            "as_of_time": _nullable({"type": "string", "description": "可选 ISO-8601 评估时间；不确定时传 null。"}),
            "window_days": {"type": "integer", "description": "回看天数。主动追奶/减奶/稳奶通常用 1；全面评估通常用 7。"},
            "include_today": {"type": "boolean", "description": "是否包含当前日未完整记录。通常评估完整日时传 false。"},
        },
    ),
    "infant_growth_evaluate": _function_tool(
        "infant_growth_evaluate",
        "EVALUATE 只读工具：基于宝宝档案、生长记录和固定参考数据返回生长趋势规则结果。不是诊断；仅在用户提到身高、体重、增长或摄入是否足够时使用。",
        {
            "infant_id": _nullable({"type": "integer", "description": "可选宝宝 ID；不确定时传 null。"}),
            "as_of_time": _nullable({"type": "string", "description": "可选 ISO-8601 评估时间；不确定时传 null。"}),
        },
    ),
    "milk_plan_preview": _function_tool(
        "milk_plan_preview",
        "PREVIEW 候选方案工具：按确定性规则生成追奶、稳奶或减奶计划草稿，不写数据库。返回候选计划结构和规则依据；保存前必须获得用户确认。",
        {
            "plan_type": {"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]},
            "plan_days": _nullable({"type": "integer"}),
            "custom_target_daily_ml": _nullable({"type": "number"}),
            "as_of_time": _nullable({"type": "string"}),
            "options": _nullable(
                {
                    **JSON_OBJECT_STRING,
                    "description": "字符串编码 JSON。可包含 prepared_assessment、prepared_growth_assessment、observed_persistent_abnormal 或 medical_confirmation_confirmed。",
                }
            ),
        },
    ),
    "milk_plan_apply": _function_tool(
        "milk_plan_apply",
        "APPLY 写入工具：保存用户已确认的奶量计划，并展开写入 calendar。有副作用；只有用户明确确认后才调用。",
        {
            "confirmed_plan": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_plan_list": _function_tool(
        "milk_plan_list",
        "GET 只读工具：列出当前用户已保存的奶量计划。只返回结构化记录，不生成计划建议。",
        {
            "plan_type": _nullable({"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]}),
            "limit": {"type": "integer"},
        },
    ),
    "milk_plan_get": _function_tool(
        "milk_plan_get",
        "GET 只读工具：读取一个已保存奶量计划；plan_id 为 null 时读取最新计划。只返回结构化记录。",
        {"plan_id": _nullable({"type": "integer"})},
    ),
    "milk_plan_delete": _function_tool(
        "milk_plan_delete",
        "DELETE 写入工具：删除已保存奶量计划，并可删除其生成的 calendar 条目。有副作用；只有用户明确确认后才调用。",
        {
            "plan_id": {"type": "integer"},
            "idempotency_key": {"type": "string"},
            "delete_calendar_items": {"type": "boolean"},
        },
    ),
    "milk_plan_update": _function_tool(
        "milk_plan_update",
        "UPDATE 写入工具：更新已保存奶量计划的元数据或替换计划 payload。有副作用；只有用户明确确认后才调用。",
        {
            "plan_id": {"type": "integer"},
            "patch": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
            "reexpand_calendar": {"type": "boolean"},
        },
    ),
    "milk_plan_regenerate_preview": _function_tool(
        "milk_plan_regenerate_preview",
        "PREVIEW 候选方案工具：基于已有计划或指定计划类型重新生成计划草稿，不写数据库。返回候选计划结构；保存或更新前必须获得用户确认。",
        {
            "plan_id": _nullable({"type": "integer"}),
            "plan_type": _nullable({"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]}),
            "plan_days": _nullable({"type": "integer"}),
            "custom_target_daily_ml": _nullable({"type": "number"}),
            "as_of_time": _nullable({"type": "string"}),
            "options": _nullable(JSON_OBJECT_STRING),
        },
    ),
    "milk_plan_target_validate": _function_tool(
        "milk_plan_target_validate",
        "VALIDATE 只读工具：校验用户主动提出的追奶、稳奶或减奶目标是否符合当前评估与参考边界。返回 valid/violations/warnings，不生成最终建议。",
        {
            "plan_type": {"type": "string", "enum": ["increase_milk", "maintain_milk", "decrease_milk"]},
            "target_daily_ml": _nullable({"type": "number"}),
            "delta_ml": _nullable({"type": "number", "description": "未提供 target_daily_ml 时使用的每日增加或减少量。"}),
            "as_of_time": _nullable({"type": "string"}),
        },
    ),
    "milk_plan_validate": _function_tool(
        "milk_plan_validate",
        "VALIDATE 只读工具：在保存或更新前校验完整奶量计划草稿，包括追奶、减奶、稳奶边界。返回 valid/violations/warnings。",
        {"plan": JSON_OBJECT_STRING},
    ),
    "milk_records_range_get": _function_tool(
        "milk_records_range_get",
        "GET 只读工具：读取任意时间段内的吸奶、亲喂、母乳瓶喂和奶粉瓶喂记录，返回结构化原始记录和聚合摘要。亲喂奶量如出现估算会明确标记为 estimated。",
        {
            "start_at": {"type": "string", "description": "起始日期或日期时间，例如 2026-05-01 或 2026-05-01 08:00。"},
            "end_at": {"type": "string", "description": "结束日期或日期时间；日期会按整天处理并作为 exclusive end 的下一日 00:00。"},
            "record_scope": {
                "type": "string",
                "enum": ["all", "milk_output", "feeding", "pumping", "nursing", "breastmilk_bottle", "formula_bottle"],
                "description": "读取范围：母乳产出用 milk_output；全部记录用 all。",
            },
            "include_raw_records": {"type": "boolean", "description": "是否返回原始记录列表；只要摘要时传 false。"},
            "summary_granularity": {"type": "string", "enum": ["none", "daily"], "description": "是否返回每日聚合。"},
            "limit": {"type": "integer", "description": "每类原始记录最多返回数量，建议 50-200。"},
        },
    ),
    "milk_record_create": _function_tool(
        "milk_record_create",
        "CREATE 写入工具：新增一条真实奶量记录，可新增吸奶、亲喂、母乳瓶喂或奶粉瓶喂。有副作用；只有用户明确确认后才调用。",
        {
            "record_kind": {"type": "string", "enum": ["pumping", "nursing", "breastmilk_bottle", "formula_bottle"]},
            "occurred_at": {"type": "string", "description": "记录发生时间，例如 2026-05-14 09:30。"},
            "amount_ml": _nullable({"type": "number", "description": "吸奶或瓶喂奶量 ml；亲喂不确定时传 null。"}),
            "duration_minutes": _nullable({"type": "integer", "description": "吸奶或亲喂持续分钟数；不确定时传 null。"}),
            "infant_id": _nullable({"type": "integer", "description": "喂养记录对应宝宝 ID；不确定时传 null。"}),
            "title": _nullable({"type": "string", "description": "可选标题或备注；无则传 null。"}),
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_record_update": _function_tool(
        "milk_record_update",
        "UPDATE 写入工具：修改一条真实奶量记录。record_id 来自 milk_records_range_get；patch 可包含 occurred_at、amount_ml、duration_minutes、record_kind、infant_id、title。有副作用；只有用户明确确认后才调用。",
        {
            "record_kind": {"type": "string", "enum": ["pumping", "nursing", "breastmilk_bottle", "formula_bottle"]},
            "record_id": {"type": "integer"},
            "patch": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_record_delete": _function_tool(
        "milk_record_delete",
        "DELETE 写入工具：删除一条真实奶量记录。record_id 来自 milk_records_range_get。有副作用；只有用户明确确认后才调用。",
        {
            "record_kind": {"type": "string", "enum": ["pumping", "nursing", "breastmilk_bottle", "formula_bottle"]},
            "record_id": {"type": "integer"},
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_today_overview_get": _function_tool(
        "milk_today_overview_get",
        "GET 只读工具：读取今日奶量管理 calendar 概览，包括总任务数、完成数、待完成数和任务列表。只返回结构化事实。",
        {
            "target_date": _nullable(ISO_DATE),
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_today_summary_get": _function_tool(
        "milk_today_summary_get",
        "GET 只读工具：读取今日日结聚合，包括 calendar、吸奶和喂养摘要。只返回结构化统计；鼓励/安抚话术由模型生成。",
        {
            "target_date": _nullable(ISO_DATE),
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_today_tasks_shift": _function_tool(
        "milk_today_tasks_shift",
        "UPDATE 写入工具：顺延今日 calendar 任务。有副作用；只有用户明确确认后才调用。",
        {
            "target_date": _nullable(ISO_DATE),
            "shift_minutes": {"type": "integer"},
            "from_time": _nullable({"type": "string", "description": "只顺延此时间之后的任务，例如 14:00；不限定时传 null。"}),
            "plan_id": _nullable({"type": "integer"}),
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_today_tasks_confirm": _function_tool(
        "milk_today_tasks_confirm",
        "UPDATE 写入受限工具：确认今日吸奶任务完成。当前默认由 handler 阻止 LLM 侧完成状态写入，并提示用户回主界面日历操作。",
        {
            "target_date": _nullable(ISO_DATE),
            "plan_id": _nullable({"type": "integer"}),
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_day_get": _function_tool(
        "milk_calendar_day_get",
        "GET 只读工具：读取某一天奶量管理 calendar 条目。只返回结构化日程事实。",
        {
            "target_date": ISO_DATE,
            "plan_id": _nullable({"type": "integer"}),
            "item_type": _nullable({"type": "string", "enum": ["吸奶", "亲喂", "自定义"]}),
        },
    ),
    "milk_calendar_range_get": _function_tool(
        "milk_calendar_range_get",
        "GET 只读工具：读取任意日期或时间范围内的奶量管理 calendar/计划执行情况，返回完成率、每日统计和可选条目列表。",
        {
            "start_at": {"type": "string", "description": "起始日期或日期时间，例如 2026-05-14 或 2026-05-14 08:00。"},
            "end_at": {"type": "string", "description": "结束日期或日期时间；日期会按整天处理并作为 exclusive end 的下一日 00:00。"},
            "plan_id": _nullable({"type": "integer"}),
            "item_type": _nullable({"type": "string", "enum": ["吸奶", "亲喂", "自定义"]}),
            "include_items": {"type": "boolean", "description": "是否返回条目列表；只要统计时传 false。"},
            "limit": {"type": "integer", "description": "最多返回条目数量，建议 50-200。"},
        },
    ),
    "milk_calendar_adjustment_preview": _function_tool(
        "milk_calendar_adjustment_preview",
        "PREVIEW 候选变更工具：预览新增事项导致的 calendar 变更，不写数据库。返回冲突、候选调整和 proposal；apply 前必须获得用户确认。",
        {
            "target_date": ISO_DATE,
            "event_start_time": {"type": "string", "description": "开始时间，例如 09:00 或完整 ISO datetime。"},
            "event_end_time": _nullable({"type": "string", "description": "结束时间，例如 09:30；如提供 duration_minutes 可传 null。"}),
            "duration_minutes": _nullable({"type": "integer"}),
            "content": {"type": "string"},
            "item_type": _nullable({"type": "string", "enum": ["吸奶", "亲喂", "自定义"], "description": "吃饭、外出、会议、接孩子等使用 自定义。"}),
            "plan_id": _nullable({"type": "integer"}),
        },
    ),
    "milk_calendar_adjustment_apply": _function_tool(
        "milk_calendar_adjustment_apply",
        "APPLY 写入工具：应用用户已确认的 calendar adjustment proposal。proposal 必须包含新增事项和相关任务调整；只有用户明确确认后才调用。",
        {
            "target_date": ISO_DATE,
            "proposal": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_range_update": _function_tool(
        "milk_calendar_range_update",
        "UPDATE/DELETE 写入工具：批量修改任意日期或时间范围内的计划条目。operation=shift 时 patch 传 {\"shift_minutes\":30}；operation=patch_items 时先读取范围再传 {\"updates\":[{\"item_id\":1,\"start_time\":\"09:00\"}]}；operation=delete 删除范围内匹配条目。有副作用；只有用户明确确认后才调用。",
        {
            "start_at": {"type": "string"},
            "end_at": {"type": "string"},
            "operation": {"type": "string", "enum": ["shift", "delete", "patch_items"]},
            "patch": JSON_OBJECT_STRING,
            "plan_id": _nullable({"type": "integer"}),
            "item_type": _nullable({"type": "string", "enum": ["吸奶", "亲喂", "自定义"]}),
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_item_update": _function_tool(
        "milk_calendar_item_update",
        "UPDATE 写入受限工具：更新 calendar 条目的时间、内容或类型。有副作用；只有用户明确确认后才调用。finish 完成状态默认拒绝并提示回主界面日历操作。",
        {
            "item_id": {"type": "integer"},
            "patch": JSON_OBJECT_STRING,
            "idempotency_key": {"type": "string"},
        },
    ),
    "milk_calendar_item_delete": _function_tool(
        "milk_calendar_item_delete",
        "DELETE 写入工具：删除一个 calendar 条目。有副作用；只有目标条目明确且用户确认后才调用。",
        {
            "item_id": {"type": "integer"},
            "idempotency_key": {"type": "string"},
        },
    ),
}
