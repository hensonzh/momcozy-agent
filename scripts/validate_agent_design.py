from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from momcozy_agent import ContextState, build_agent_request, execute_skill_runtime_tool, execute_tool
from momcozy_agent.server import _runtime_inputs_from_ag_ui


def main() -> None:
    initial_request = build_agent_request(
        {
            "user_message": "我需要 IBCLC 帮忙，我的吸奶量下降了。",
            "locale": "zh-CN",
            "timezone": "America/Los_Angeles",
            "message_sent_at": "2026-05-04T09:00:00-07:00",
        }
    )
    initial_tool_names = {tool["name"] for tool in initial_request["tools"] if tool["type"] == "function"}
    initial_tool_types = {tool["type"] for tool in initial_request["tools"]}
    initial_deferred_tool_names = _deferred_tool_names(initial_request)
    assert "metadata" not in initial_request, "request metadata should no longer carry loaded_skill_ids"
    assert [item.get("role", item.get("type")) for item in initial_request["input"]] == ["user"]
    assert len(initial_request["input"][0]["content"]) == 2
    assert initial_request["input"][0]["content"][0]["text"].startswith("request_context:")
    assert "service_selection: model_selects_service_skill_from_manifest" in initial_request["instructions"]
    assert "skill_manifest:" in initial_request["instructions"]
    assert "global_safety_policy:" in initial_request["instructions"]
    assert "全局响应风格设计" in initial_request["instructions"]
    assert "先接住人，再处理事" in initial_request["instructions"]
    assert "适用于所有服务" in initial_request["instructions"]
    assert "人味与共鸣写法" in initial_request["instructions"]
    assert "共鸣不是一句客套话" in initial_request["instructions"]
    assert "最终回复可见性规则" in initial_request["instructions"]
    assert "不要把情绪承接、安全边界、关键澄清或下一步行动只写在工具调用前" in initial_request["instructions"]
    assert "中性事实、普通问候、简单确认" in initial_request["instructions"]
    assert "不强行煽情" in initial_request["instructions"]
    assert "如果本轮有情绪、紧迫、挫败或风险感" in initial_request["instructions"]
    assert "先表达轻柔祝贺" in initial_request["instructions"]
    assert "最终回复必须先轻柔祝贺并简短共鸣" in initial_request["instructions"]
    assert "最终一轮面向用户的回复必须按上面的响应优先级重新组织" in initial_request["instructions"]
    assert "最终一轮面向用户的回复必须重新自然体现情绪承接" not in initial_request["instructions"]
    assert "我要生孩子了" in initial_request["instructions"]
    assert "物品准备类问题" in initial_request["instructions"]
    assert "去医院前准备什么/提前准备些什么/要带什么" in initial_request["instructions"]
    assert "按待产包服务处理" in initial_request["instructions"]
    assert "入院时机、症状判断或风险不确定问题" in initial_request["instructions"]
    assert "服务邀约后的短确认承接协议" in initial_request["instructions"]
    assert "单一、明确的服务动作" in initial_request["instructions"]
    assert "多个服务选项" in initial_request["instructions"]
    assert "skill_manifest:" not in initial_request["input"][0]["content"][0]["text"]
    assert initial_request["input"][0]["content"][1]["text"].startswith("user_message:")
    assert "tool_search" in initial_tool_types
    assert "load_skill" in initial_tool_names
    assert "ui_form_create" in initial_tool_names
    assert "ui_card_create" in initial_tool_names
    assert "ibclc_consult_card_create" in initial_tool_names
    assert "memory_search" not in initial_tool_names
    assert "handoff_summary_generate" not in initial_tool_names
    assert "handoff_summary_generate" in initial_deferred_tool_names
    assert "support_ticket_draft_create" not in initial_tool_names
    assert "support_ticket_draft_create" in initial_deferred_tool_names
    assert "device_manual_search" not in initial_tool_names
    assert "device_manual_search" in initial_deferred_tool_names
    assert "milk_snapshot_get" not in initial_tool_names
    assert "milk_snapshot_get" in initial_deferred_tool_names
    assert "milk_context_get" not in initial_deferred_tool_names
    assert "milk_plan_preview" not in initial_tool_names
    assert "milk_plan_preview" in initial_deferred_tool_names
    assert "milk_calendar_mutate" not in initial_tool_names
    assert "milk_calendar_mutate" in initial_deferred_tool_names
    assert "milk_calendar_adjustment_apply" not in initial_deferred_tool_names
    expected_milk_deferred_tools = {
        "milk_snapshot_get",
        "milk_assessment_evaluate",
        "infant_growth_evaluate",
        "milk_records_query",
        "milk_record_mutate",
        "milk_plan_query",
        "milk_plan_preview",
        "milk_plan_mutate",
        "milk_calendar_query",
        "milk_calendar_change_preview",
        "milk_calendar_mutate",
    }
    assert expected_milk_deferred_tools <= initial_deferred_tool_names
    for removed_tool_name in (
        "ibclc_book",
        "reminder_create",
        "memory_write",
        "knowledge_search",
        "support_ticket_create",
        "support_ticket_submit",
        "risk_evaluate",
        "feeding_log_query",
        "pumping_log_query",
        "trend_calculate",
        "milk_context_get",
        "milk_plan_apply",
        "milk_plan_list",
        "milk_plan_get",
        "milk_plan_delete",
        "milk_plan_update",
        "milk_plan_regenerate_preview",
        "milk_plan_target_validate",
        "milk_plan_validate",
        "milk_records_range_get",
        "milk_record_create",
        "milk_record_update",
        "milk_record_delete",
        "milk_today_overview_get",
        "milk_today_summary_get",
        "milk_today_tasks_shift",
        "milk_today_tasks_confirm",
        "milk_calendar_day_get",
        "milk_calendar_range_get",
        "milk_calendar_adjustment_preview",
        "milk_calendar_adjustment_apply",
        "milk_calendar_range_update",
        "milk_calendar_item_update",
        "milk_calendar_item_delete",
    ):
        assert removed_tool_name not in initial_tool_names
        assert removed_tool_name not in initial_deferred_tool_names

    image_data_url = "data:image/png;base64,iVBORw0KGgo="
    image_payload = {
        "threadId": "thread_image_test",
        "userId": "user_demo",
        "state": {
            "user_id": "user_demo",
            "locale": "zh-CN",
            "timezone": "America/Los_Angeles",
            "message_sent_at": "2026-05-04T09:00:00-07:00",
        },
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "帮我看看这个吸奶器配件怎么装"},
                    {"type": "image", "image_url": image_data_url, "mime_type": "image/png", "name": "pump.png", "size": 24},
                ],
            }
        ],
    }
    image_inputs = _runtime_inputs_from_ag_ui(image_payload)
    assert image_inputs["user_id"] == "user_demo"
    assert image_inputs["user_profile"]["user_id"] == "user_demo"
    assert image_inputs["user_message"] == "帮我看看这个吸奶器配件怎么装"
    assert image_inputs["images"][0]["image_url"] == image_data_url
    image_request = build_agent_request(image_inputs)
    image_content = image_request["input"][0]["content"]
    assert image_content[0]["type"] == "input_text"
    assert image_content[1]["type"] == "input_text"
    assert image_content[2] == {"type": "input_image", "image_url": image_data_url, "detail": "auto"}

    loaded = execute_skill_runtime_tool("load_skill", {"skill_id": "milk-management"})
    assert "# 奶量管理" in loaded["skill_md"]
    assert "tool_names" not in loaded, "load_skill must not advertise per-skill tool_names"
    assert loaded["id"] == "milk-management"
    assert loaded["name"] == "milk-management"
    assert isinstance(loaded["description"], str) and loaded["description"]

    birth_prep_skill = execute_skill_runtime_tool("load_skill", {"skill_id": "birth-prep"})
    assert "临产表达的回应节奏" in birth_prep_skill["skill_md"]
    assert "第一反应不是清单" in birth_prep_skill["skill_md"]
    assert "在最终回复里先轻柔祝贺" in birth_prep_skill["skill_md"]
    assert "最终回复先表达祝贺和情感共鸣" in birth_prep_skill["skill_md"]
    assert "先恭喜你，宝宝可能快要来了" in birth_prep_skill["skill_md"]
    assert "服务邀约承接" in birth_prep_skill["skill_md"]
    assert "待产包服务入口确认" in birth_prep_skill["skill_md"]
    assert "默认先不调用 `ui_form_create`" in birth_prep_skill["skill_md"]
    assert "已有信息会先填好" in birth_prep_skill["skill_md"]
    assert "字段的 `default_value`" in birth_prep_skill["skill_md"]
    assert 'ui_form_create(form_id="hospital_bag_intake")' in birth_prep_skill["skill_md"]
    birth_plan_reference = execute_skill_runtime_tool(
        "read_skill_file",
        {"skill_id": "birth-prep", "kind": "references", "path": "references/birth-plan-card.md"},
    )["content"]
    assert "创建 `ui_form_create` 后，最终回复里输出一句简短引导" in birth_plan_reference
    assert "只放在工具调用前的中间态" in birth_plan_reference
    hospital_bag_reference = execute_skill_runtime_tool(
        "read_skill_file",
        {"skill_id": "birth-prep", "kind": "references", "path": "references/hospital-bag-service.md"},
    )["content"]
    assert "基本信息｜预产期或当前孕周" in hospital_bag_reference
    assert "生产信息｜计划分娩方式" in hospital_bag_reference
    assert "医院信息｜已知医院会提供的物品" in hospital_bag_reference
    assert "偏好信息｜喂养意向" in hospital_bag_reference
    assert "BMI 或身高体重情况" in hospital_bag_reference
    assert "不要创建仅用于装饰的假字段" in hospital_bag_reference
    assert "首次进入待产包服务时先做服务邀约，不直接创建表单" in hospital_bag_reference
    assert "用户确认开始后，再创建 `hospital_bag_intake` 表单" in hospital_bag_reference
    assert "`description`: 留空字符串" in hospital_bag_reference
    assert "先确认几件关键背景" not in hospital_bag_reference
    assert "default_value" in hospital_bag_reference
    assert "已知孕周或预产期 -> `due_date_or_week.default_value`" in hospital_bag_reference
    assert "未知信息不要编造默认值" in hospital_bag_reference
    assert "packing_style" not in hospital_bag_reference
    assert "hospital_rules_or_notes" not in hospital_bag_reference
    assert "existing_checklist_or_photo_note" not in hospital_bag_reference
    assert "已知医院规则或注意事项" not in hospital_bag_reference
    assert "已有医院清单或产检材料说明" not in hospital_bag_reference
    assert "清单风格" not in hospital_bag_reference
    assert "极简" not in hospital_bag_reference
    assert "预算优先" not in hospital_bag_reference

    prefilled_hospital_bag_form = execute_tool(
        "ui_form_create",
        {
            "form_id": "hospital_bag_intake",
            "title": "信息采集",
            "description": "先确认几件关键背景，帮你少带错、少漏带。",
            "submit_label": "生成我的卡片",
            "fields": [
                {
                    "id": "due_date_or_week",
                    "label": "基本信息｜预产期或当前孕周",
                    "type": "text",
                    "required": True,
                    "default_value": "37 周",
                },
                {
                    "id": "birth_path",
                    "label": "生产信息｜计划分娩方式",
                    "type": "select",
                    "required": True,
                    "options": ["顺产", "刨腹产", "未确定"],
                    "default_value": "顺产",
                },
                {
                    "id": "hospital_rules_or_notes",
                    "label": "医院信息｜已知医院规则或注意事项",
                    "type": "textarea",
                    "required": False,
                },
                {
                    "id": "existing_checklist_or_photo_note",
                    "label": "医院信息｜已有医院清单或产检材料说明",
                    "type": "textarea",
                    "required": False,
                },
            ],
        },
        {
            "user_message": "好",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "message_sent_at": "2026-05-04T20:00:00+08:00",
        },
    )
    prefilled_fields = {field["id"]: field for field in prefilled_hospital_bag_form["form"]["fields"]}
    assert prefilled_hospital_bag_form["form"]["description"] == ""
    assert prefilled_fields["due_date_or_week"]["default_value"] == "37 周"
    assert prefilled_fields["birth_path"]["default_value"] == "顺产"
    assert "hospital_rules_or_notes" not in prefilled_fields
    assert "existing_checklist_or_photo_note" not in prefilled_fields

    pump_skill = execute_skill_runtime_tool("load_skill", {"skill_id": "device-guidance"})
    assert "references/air1/faq.md" in pump_skill["references"]
    assert "references/air1/manual.md" in pump_skill["references"]
    assert "device_manual_search" in pump_skill["skill_md"]

    air1_manual = execute_tool(
        "device_manual_search",
        {"model": "Air1", "query": "Air1 怎么清洗和消毒？", "topic": "cleaning", "max_results": 3},
        {"user_message": "Air1 怎么清洗？", "locale": "zh-CN", "timezone": "America/Los_Angeles", "message_sent_at": "2026-05-04T09:00:00-07:00"},
    )
    assert air1_manual["status"] in {"manual_loaded", "manual_loaded_with_faq"}
    assert air1_manual["manual"]
    assert "清洁" in air1_manual["manual"]["content"]
    assert "消毒" in air1_manual["manual"]["content"]

    unsupported_device = execute_tool(
        "device_manual_search",
        {"model": "unknown", "query": "Air1 第一次开箱怎么用？", "topic": "unboxing", "max_results": 2},
        {"user_message": "Air1 第一次开箱怎么用？", "locale": "zh-CN", "timezone": "America/Los_Angeles", "message_sent_at": "2026-05-04T09:00:00-07:00"},
    )
    assert unsupported_device["status"] == "unsupported_model"
    assert unsupported_device["results"] == []

    low_confidence_device = execute_tool(
        "device_manual_search",
        {"model": "Air1", "query": "完全无关的问题", "topic": "other", "max_results": 2},
        {"user_message": "完全无关的问题", "locale": "zh-CN", "timezone": "America/Los_Angeles", "message_sent_at": "2026-05-04T09:00:00-07:00"},
    )
    assert low_confidence_device["status"] == "manual_loaded"
    assert low_confidence_device["match_score"] == 0
    assert low_confidence_device["manual"], "manual should still load even when FAQ retrieval has no match"
    assert low_confidence_device["faq_results"] == []

    hospital_bag_card = execute_tool(
        "ui_card_create",
        {
            "card_type": "hospital_bag_card",
            "schema_version": "1.0",
            "card_json": {
                "title": "待产包",
                "packing_groups": [
                    {"group_id": "documents", "title": "证件资料包", "items": []},
                    {"group_id": "baby", "title": "宝宝出院包", "items": []},
                ],
            },
        },
        {"user_message": "confirmed_form_data:\n{}", "locale": "zh-CN", "timezone": "America/Los_Angeles", "message_sent_at": "2026-05-04T09:00:00-07:00"},
    )
    card_json = hospital_bag_card["card"]["card_json"]
    postpartum_groups = [group for group in card_json["packing_groups"] if group.get("group_id") == "postpartum"]
    assert postpartum_groups, "hospital bag card should include a postpartum/mom admission group"
    pump_item_index = next(
        index
        for index, item in enumerate(postpartum_groups[0]["items"])
        if "吸奶" in item["label"]
    )
    assert pump_item_index < 4, "吸奶器应在紧凑版卡片中保持可见"
    assert "assistant_followup" in hospital_bag_card
    assert "/hospital-bag-cart" in hospital_bag_card["assistant_followup"]["message"]
    assert "一键打包下单页" in hospital_bag_card["assistant_followup"]["message"]

    birth_plan_card = execute_tool(
        "ui_card_create",
        {
            "card_type": "birth_plan_card",
            "schema_version": "1.0",
            "card_json": {
                "title": "分娩沟通卡",
                "owner": {"due_date_or_week": "37 周", "support_people": ["伴侣"]},
                "birth_preferences": {"birth_path": "顺产", "environment": "待确认"},
                "communication_preferences": {
                    "decision_style": "先解释",
                    "consent_preference": "必须征求同意",
                    "language_or_explanation_preference": "语言简单清楚",
                },
                "questions_for_hospital": ["陪同规则？", "入院流程？", "宝宝护理流程？", "住院天数？"],
                "medical_notes": {"conditions_or_constraints": "不应保留模型推断出的医疗备注"},
                "missing_fields": ["待确认"],
            },
        },
        {
            "user_message": (
                "confirmed_form_data:\n"
                '{"due_date_or_week":"37 周","birth_path":"顺产","top_priorities":"希望每一步先解释；希望伴侣参与重要决定",'
                '"communication_preferences":["干预前先解释","先征求同意"],"support_people":"伴侣",'
                '"medical_notes":"青霉素过敏"}'
            ),
            "locale": "zh-CN",
            "timezone": "America/Los_Angeles",
            "message_sent_at": "2026-05-04T09:00:00-07:00",
        },
    )
    birth_card_json = birth_plan_card["card"]["card_json"]
    assert birth_card_json["top_priorities"] == ["希望每一步先解释", "希望伴侣参与重要决定"]
    assert birth_card_json["overview"]["birth_path"] == "顺产"
    assert len(birth_card_json["questions_for_hospital"]) == 3
    assert birth_card_json["medical_notes"] == ["青霉素过敏"]
    assert "missing_fields" not in birth_card_json
    assert "assistant_followup" in birth_plan_card
    assert "提前和医院确认" in birth_plan_card["assistant_followup"]["message"]

    support_ticket_draft = execute_tool(
        "support_ticket_draft_create",
        {
            "issue_type": "设备故障",
            "issue_summary": "吸奶器反复无法启动，用户已经重装配件仍未解决。",
            "product_model": "M5",
            "order_number": None,
            "purchase_channel": None,
            "user_contact": None,
            "troubleshooting_done": ["重启设备", "重新安装配件"],
            "urgency": "high",
            "user_emotion": "挫败",
            "attachments_note": "用户已上传设备图片",
        },
        {"user_message": "我真的搞不定这个吸奶器了", "locale": "zh-CN", "timezone": "America/Los_Angeles", "message_sent_at": "2026-05-04T09:00:00-07:00"},
    )
    assert support_ticket_draft["status"] == "ticket_draft_created"
    assert support_ticket_draft["ticket"]["issue_type"] == "设备故障"
    assert support_ticket_draft["ticket"]["troubleshooting_done"] == ["重启设备", "重新安装配件"]

    ibclc_card = execute_tool(
        "ibclc_consult_card_create",
        {
            "consultant_name": None,
            "consultant_bio": None,
            "chat_url": None,
        },
        {"user_message": "我想找 IBCLC 看看乳头疼", "locale": "zh-CN", "timezone": "America/Los_Angeles", "message_sent_at": "2026-05-04T09:00:00-07:00"},
    )
    assert ibclc_card["status"] == "ibclc_consult_card_created"
    assert ibclc_card["card"]["card_type"] == "ibclc_consult_card"
    assert ibclc_card["card"]["consultant"]["name"] == "Emily Chen"
    assert ibclc_card["card"]["consultant"]["bio"]
    assert ibclc_card["card"]["chat"]["url"] == "/ibclc-chat.html"

    loaded_request = build_agent_request(
        {
            "user_message": "我需要 IBCLC 帮忙，我的吸奶量下降了。",
            "locale": "zh-CN",
            "timezone": "America/Los_Angeles",
            "message_sent_at": "2026-05-04T09:01:00-07:00",
        },
        {"loaded_skill_ids": ["milk-management"]},
    )
    loaded_tool_names = {tool["name"] for tool in loaded_request["tools"] if tool["type"] == "function"}
    loaded_deferred_tool_names = _deferred_tool_names(loaded_request)
    assert initial_request["tools"] == loaded_request["tools"]
    assert "handoff_summary_generate" not in loaded_tool_names
    assert "handoff_summary_generate" in loaded_deferred_tool_names
    assert "pumping_log_query" not in loaded_tool_names
    assert "pumping_log_query" not in loaded_deferred_tool_names
    assert "<loaded_skill_context>" not in loaded_request["input"][0]["content"][0]["text"]

    context_state = ContextState()
    first_stateful_request = build_agent_request(
        {
            "user_message": "帮我准备待产包",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "message_sent_at": "2026-05-04T20:00:00+08:00",
        },
        {"context_state": context_state},
    )
    first_context = first_stateful_request["input"][0]["content"][0]["text"]
    assert first_context.startswith("request_context:")
    assert "locale: zh-CN" in first_context
    assert "timezone: Asia/Shanghai" in first_context
    assert "message_sent_at: 2026-05-04T20:00:00+08:00" in first_context
    assert "current_date:" not in first_context
    assert context_state.environment_sent

    second_stateful_request = build_agent_request(
        {
            "user_message": "我现在是 36 周",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "message_sent_at": "2026-05-04T20:01:00+08:00",
            "previous_response_id": "resp_previous",
        },
        {"context_state": context_state},
    )
    second_context = second_stateful_request["input"][0]["content"][0]["text"]
    assert second_context.startswith("request_context:")
    assert "skill_manifest:" not in second_context
    assert "service_selection: model_selects_service_skill_from_manifest" not in second_context
    assert "<loaded_skill_context>" not in second_context
    assert "locale:" not in second_context
    assert "timezone:" not in second_context
    assert "message_sent_at: 2026-05-04T20:01:00+08:00" in second_context

    loaded_stateful_request = build_agent_request(
        {
            "user_message": "继续",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "message_sent_at": "2026-05-04T20:02:00+08:00",
            "previous_response_id": "resp_previous",
        },
        {"context_state": context_state, "loaded_skill_ids": ["birth-prep"]},
    )
    loaded_context = loaded_stateful_request["input"][0]["content"][0]["text"]
    assert "<loaded_skill_context_delta>" not in loaded_context
    assert "<loaded_skill_context>" not in loaded_context
    assert "# Birth Prep" not in loaded_context

    profile_state = ContextState()
    build_agent_request(
        {
            "user_message": "我想做 birth plan",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "message_sent_at": "2026-05-04T20:00:00+08:00",
            "user_profile": {
                "pregnancy_status": "pregnant",
                "due_date": "2026-06-10",
                "language": "zh-CN",
            },
        },
        {"context_state": profile_state},
    )
    profile_context_request = build_agent_request(
        {
            "user_message": "继续",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "message_sent_at": "2026-05-04T20:01:00+08:00",
            "previous_response_id": "resp_previous",
            "user_profile": {
                "pregnancy_status": "pregnant",
                "due_date": "2026-06-10",
                "language": "zh-CN",
            },
        },
        {"context_state": profile_state},
    )
    profile_context = profile_context_request["input"][0]["content"][0]["text"]
    assert "<context_ledger_delta>" not in profile_context
    assert "<context_invalidations>" not in profile_context
    assert "user_profile.due_date" not in profile_context
    assert "2026-06-10" not in profile_context

    service_skills = execute_skill_runtime_tool("list_skills", {})["skills"]
    service_skill_ids = {skill["id"] for skill in service_skills}
    assert service_skill_ids == {"birth-prep", "milk-management", "emotion-support", "device-guidance"}
    for skill in service_skills:
        allowed_manifest_keys = {"id", "name", "description", "safety_limits"}
        assert set(skill.keys()) <= allowed_manifest_keys, (
            f"Unexpected manifest keys for {skill['id']}: {sorted(skill.keys())}"
        )
        assert isinstance(skill["safety_limits"], list) and skill["safety_limits"], (
            f"{skill['id']} must declare safety_limits in SKILL.md frontmatter"
        )
        skill_doc = execute_skill_runtime_tool("load_skill", {"skill_id": skill["id"]})["skill_md"]
        assert "全局响应风格" in skill_doc, (
            f"{skill['id']} must explicitly inherit the global response style"
        )
        assert "服务邀约承接" in skill_doc, (
            f"{skill['id']} must define how short confirmations continue service offers"
        )

    _assert_strict_function_schemas(initial_request["tools"])

    print("Agent design checks passed.")


def _assert_strict_function_schemas(tools: list[dict]) -> None:
    for tool in tools:
        if tool.get("type") == "function":
            _assert_strict_object_schema(tool["parameters"], path=tool["name"])
        elif tool.get("type") == "namespace":
            for child in tool.get("tools", []):
                _assert_strict_object_schema(child["parameters"], path=child["name"])


def _assert_strict_object_schema(schema: dict, *, path: str) -> None:
    types = schema.get("type")
    if types == "object" or (isinstance(types, list) and "object" in types):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        assert sorted(required) == sorted(properties.keys()), (
            f"strict mode requires every property to be required at {path}: {sorted(properties.keys())} vs {sorted(required)}"
        )
        assert schema.get("additionalProperties") is False, f"strict mode requires additionalProperties=false at {path}"
        for prop_name, prop_schema in properties.items():
            if isinstance(prop_schema, dict):
                _assert_strict_object_schema(prop_schema, path=f"{path}.{prop_name}")
    if types == "array" or (isinstance(types, list) and "array" in types):
        items = schema.get("items")
        if isinstance(items, dict):
            _assert_strict_object_schema(items, path=f"{path}[]")


def _deferred_tool_names(request: dict) -> set[str]:
    names: set[str] = set()
    for tool in request["tools"]:
        if tool.get("type") != "namespace":
            continue
        for child_tool in tool.get("tools", []):
            if child_tool.get("defer_loading") and child_tool.get("name"):
                names.add(child_tool["name"])
    return names


if __name__ == "__main__":
    main()
