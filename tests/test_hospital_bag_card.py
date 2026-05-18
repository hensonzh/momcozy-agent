from __future__ import annotations

import unittest

from momcozy_agent.tool_handlers.cards import create_card


class HospitalBagCardTests(unittest.TestCase):
    def test_adds_breast_pump_with_quantity_to_lactation_group(self) -> None:
        card_json = {
            "packing_groups": [
                {"group_id": "lactation", "title": "哺乳用品", "items": []},
            ]
        }

        result = create_card(
            {
                "card_type": "hospital_bag_card",
                "schema_version": "1.0",
                "card_json": card_json,
            },
            {"user_message": 'confirmed_form_data:\n{"feeding_intention": "母乳"}'},
        )

        items = result["card"]["card_json"]["packing_groups"][0]["items"]
        pump = next(item for item in items if "吸奶器" in item["label"])
        self.assertEqual(pump["quantity"], "1台")
        self.assertEqual(pump["priority"], "recommended")
        self.assertIn("assistant_followup", result)

    def test_formula_feeding_does_not_add_breast_pump(self) -> None:
        card_json = {
            "packing_groups": [
                {"group_id": "lactation", "title": "哺乳用品", "items": []},
            ]
        }

        result = create_card(
            {
                "card_type": "hospital_bag_card",
                "schema_version": "1.0",
                "card_json": card_json,
            },
            {"user_message": 'confirmed_form_data:\n{"feeding_intention": "配方"}'},
        )

        items = result["card"]["card_json"]["packing_groups"][0]["items"]
        self.assertEqual(items, [])
        self.assertNotIn("assistant_followup", result)


if __name__ == "__main__":
    unittest.main()
