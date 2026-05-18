from __future__ import annotations

import unittest

from momcozy_agent.tool_handlers.cards import create_card


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
        self.assertEqual(card["overview"]["birth_path"], "刨腹产")
        self.assertEqual(card["overview"]["birth_setting"], "市妇幼")
        self.assertTrue(any("37周、刨腹产" in item for item in card["personalized_notes"]))
        self.assertEqual(card["top_priorities"], ["在侧切前，请先和我沟通。"])
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
        self.assertTrue(any("疼痛管理" in item for item in card["questions_for_hospital"]))

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


if __name__ == "__main__":
    unittest.main()
