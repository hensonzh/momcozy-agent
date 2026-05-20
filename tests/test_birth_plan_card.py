from __future__ import annotations

import unittest

from momcozy_agent.tool_handlers.cards import create_card, create_form


class BirthPlanCardTests(unittest.TestCase):
    def test_normalizes_birth_plan_card_for_chinese_mobile_rendering(self) -> None:
        card_json = {
            "title": "Birth Plan Card",
            "subtitle": "Labor room communication priority card",
            "top_priorities": ["拒绝侧切"],
            "baby_after_birth": ["skin-to-skin"],
            "medical_notes": ["模型生成的医疗备注不应进入卡片"],
            "disclaimer": "This card is for communication only. Please follow clinician and hospital guidance.",
        }

        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": card_json,
            },
            {
                "user_message": (
                    "confirmed_form_data:\n"
                    '{"due_date_or_week":"37周","birth_path":"剖腹产","birth_setting":"市妇幼","support_people":"伴侣",'
                    '"medical_notes":"青霉素过敏"}'
                )
            },
        )

        card = result["card"]["card_json"]
        self.assertEqual(card["title"], "分娩沟通卡")
        self.assertEqual(card["subtitle"], "产房沟通优先级卡片")
        self.assertEqual(card["overview"]["birth_path"], "剖宫产")
        self.assertEqual(card["overview"]["birth_setting"], "市妇幼")
        self.assertTrue(any("37周、剖宫产" in item for item in card["personalized_notes"]))
        self.assertEqual(card["top_priorities"], ["在侧切前，请先和我沟通。"])
        self.assertIn("在侧切前，请先和我沟通", card["intervention_preferences"])
        self.assertEqual(card["baby_after_birth"], ["出生后尽早肌肤接触"])
        self.assertEqual(card["medical_notes"], ["青霉素过敏"])
        self.assertEqual(card["disclaimer"], "这张卡只用于沟通。请优先遵循医生和医院建议，尤其是因安全原因需要调整计划时。")
        self.assertTrue(any("术后接触宝宝" in item for item in card["questions_for_hospital"]))
        self.assertIn("assistant_followup", result)

    def test_keeps_medical_notes_empty_without_user_confirmed_facts(self) -> None:
        card_json = {
            "medical_notes": ["医生建议立即改用某方案"],
        }

        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": card_json,
            },
            {"user_message": 'confirmed_form_data:\n{"birth_path":"顺产"}'},
        )

        card = result["card"]["card_json"]
        self.assertEqual(card["overview"]["birth_path"], "顺产")
        self.assertEqual(card["medical_notes"], [])
        self.assertTrue(any("疼痛缓解" in item for item in card["questions_for_hospital"]))

    def test_deduplicates_numbered_top_priorities(self) -> None:
        card_json = {
            "top_priorities": ["希望伴侣参与重要决定", "1. 希望伴侣参与重要决定"],
        }

        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": card_json,
            },
            {"user_message": 'confirmed_form_data:\n{"birth_path":"顺产"}'},
        )

        card = result["card"]["card_json"]
        self.assertEqual(card["top_priorities"], ["希望伴侣参与重要决定"])

    def test_birth_plan_form_strips_help_text_and_keeps_group_labels(self) -> None:
        result = create_form(
            {
                "form_id": "birth_plan_card_intake",
                "title": "信息采集",
                "description": "确认几个关键信息后，我会整理成沟通卡。",
                "fields": [
                    {
                        "id": "due_date_or_week",
                        "label": "基本信息｜现在怀孕多久/预产期",
                        "type": "text",
                        "required": True,
                        "help_text": "不应进入前端。",
                    },
                    {
                        "id": "top_priorities",
                        "label": "支持与沟通｜最希望医护知道的事",
                        "type": "multi_select",
                        "required": True,
                        "options": ["希望每一步先解释", "我还没想好，请帮我整理成温和版本", "未确定"],
                        "help_text": "不应进入前端。",
                    },
                ],
            },
            {"user_message": "帮我做分娩计划卡"},
        )

        fields = result["form"]["fields"]
        self.assertEqual(result["form"]["description"], "")
        self.assertEqual(fields[0]["label"], "基本信息｜现在怀孕多久/预产期")
        self.assertEqual(fields[1]["label"], "支持与沟通｜最希望医护知道的事")
        self.assertEqual(fields[1]["options"], ["希望每一步先解释"])
        self.assertTrue(all("help_text" not in field for field in fields))

    def test_birth_plan_uses_priority_notes_and_hospital_question_focus(self) -> None:
        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": {"top_priorities": []},
            },
            {
                "user_message": (
                    "confirmed_form_data:\n"
                    '{"birth_path":"顺产","top_priorities":["希望每一步先解释"],'
                    '"priority_notes":"希望重要决定也问一下我的伴侣",'
                    '"hospital_questions_focus":["无痛或麻醉什么时候可以沟通","产后有没有母乳喂养支持"]}'
                )
            },
        )

        card = result["card"]["card_json"]
        self.assertIn("希望重要决定也问一下我的伴侣", card["top_priorities"])
        self.assertIn("无痛或麻醉什么时候可以沟通", card["questions_for_hospital"])
        self.assertIn("产后有没有母乳喂养支持", card["questions_for_hospital"])

    def test_birth_plan_prefers_unified_support_person_field(self) -> None:
        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": {},
            },
            {"user_message": 'confirmed_form_data:\n{"birth_path":"顺产","support_person":"伴侣"}'},
        )

        card = result["card"]["card_json"]
        self.assertEqual(card["overview"]["support_people"], "伴侣")
        self.assertTrue(any("伴侣" in item for item in card["personalized_notes"]))

    def test_birth_plan_maps_expanded_preference_fields(self) -> None:
        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": {},
            },
            {
                "user_message": (
                    "confirmed_form_data:\n"
                    '{"birth_path":"顺产","first_birth":"是",'
                    '"labor_preferences":["医生允许时，希望可以走动或换姿势"],'
                    '"intervention_preferences":["如果需要侧切，请先说明原因再和我沟通"],'
                    '"pain_relief_preferences":["想提前了解有哪些减痛/麻醉选择"],'
                    '"pain_relief_notes":"我有点怕疼，希望有人先解释",'
                    '"feeding_intention":"母乳",'
                    '"baby_after_birth_preferences":["如果医院允许，希望晚一点剪脐带","希望宝宝尽量和我在一起"],'
                    '"emergency_authorization":"希望先联系我的伴侣/支持人",'
                    '"hospital_questions_focus":["生产时能不能喝水或吃点东西","紧急情况会怎么沟通和决定"]}'
                )
            },
        )

        card = result["card"]["card_json"]
        self.assertIn("医生允许时，希望可以走动或换姿势", card["labor_preferences"])
        self.assertTrue(any("侧切" in item for item in card["intervention_preferences"]))
        self.assertIn("想提前了解有哪些减痛/麻醉选择", card["pain_relief"])
        self.assertIn("喂养意向：母乳", card["baby_after_birth"])
        self.assertIn("希望先联系我的伴侣/支持人", card["emergency_authorization"])
        self.assertIn("生产时能不能喝水或吃点东西", card["questions_for_hospital"])
        self.assertFalse(any("分娩沟通卡" in item for item in card["questions_for_hospital"]))
        self.assertTrue(any("第一胎" in item for item in card["personalized_notes"]))

    def test_birth_plan_maps_top_priorities_into_display_groups(self) -> None:
        result = create_card(
            {
                "card_type": "birth_plan_card",
                "schema_version": "1.0",
                "card_json": {},
            },
            {
                "user_message": (
                    "confirmed_form_data:\n"
                    '{"birth_path":"顺产","top_priorities":['
                    '"宝宝出生后，想尽早抱一抱/贴一贴",'
                    '"想尽早试着喂母乳",'
                    '"希望伴侣/支持人尽量陪在身边"]}'
                )
            },
        )

        card = result["card"]["card_json"]
        self.assertIn("出生后希望尽早肌肤接触", card["baby_after_birth"])
        self.assertIn("希望尽早尝试母乳", card["baby_after_birth"])
        self.assertIn("重要决定请同步伴侣/支持人", card["communication"])


if __name__ == "__main__":
    unittest.main()
