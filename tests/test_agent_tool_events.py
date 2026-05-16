from __future__ import annotations

import json
import unittest

from momcozy_agent.agents import (
    run_agent_loop,
    tool_call_args_event,
    tool_call_end_event,
    tool_call_result_event,
)


class AgentToolEventTests(unittest.TestCase):
    def test_tool_call_phase_events_include_tool_name(self) -> None:
        args_event = tool_call_args_event(
            "call-1",
            "milk_plan_preview",
            {"plan_type": "increase_milk"},
            response_id="resp-1",
            output_index=0,
            item_id="item-1",
        )
        end_event = tool_call_end_event(
            "call-1",
            "milk_plan_preview",
            response_id="resp-1",
            output_index=0,
            item_id="item-1",
        )
        result_event = tool_call_result_event(
            "message-1",
            "call-1",
            "milk_plan_preview",
            {"ok": True, "tool_name": "milk_plan_preview", "result": {"status": "plan_preview_ready"}},
            response_id="resp-1",
            output_index=0,
            item_id="item-1",
        )

        self.assertEqual(args_event["tool_call_name"], "milk_plan_preview")
        self.assertEqual(end_event["tool_call_name"], "milk_plan_preview")
        self.assertEqual(result_event["tool_call_name"], "milk_plan_preview")
        self.assertEqual(json.loads(result_event["content"])["tool_name"], "milk_plan_preview")

    def test_loop_emits_single_status_channel_and_explicit_artifact_events(self) -> None:
        client = _FakeClient(
            [
                {
                    "id": "resp-tool",
                    "output": [
                        {
                            "type": "function_call",
                            "id": "item-1",
                            "call_id": "call-1",
                            "name": "support_ticket_draft_create",
                            "arguments": json.dumps(
                                {
                                    "issue_type": "malfunction",
                                    "issue_summary": "吸奶器无法启动",
                                    "urgency": "normal",
                                }
                            ),
                        }
                    ],
                },
                {"id": "resp-final", "output": []},
            ]
        )
        events: list[dict[str, object]] = []

        run_agent_loop(
            client,
            {"user_message": "帮我提交售后", "locale": "zh-CN"},
            on_ag_ui_event=events.append,
            ag_ui_thread_id="thread-1",
            ag_ui_run_id="run-1",
        )

        event_types = [str(event.get("type")) for event in events]
        self.assertNotIn("ACTIVITY_SNAPSHOT", event_types)
        self.assertIn("CUSTOM", event_types)
        self.assertIn("TOOL_CALL_RESULT", event_types)
        self.assertIn("ARTIFACT_CREATED", event_types)
        self.assertIn("CONFIRMATION_REQUIRED", event_types)
        self.assertLess(event_types.index("TOOL_CALL_RESULT"), event_types.index("ARTIFACT_CREATED"))
        self.assertLess(event_types.index("ARTIFACT_CREATED"), event_types.index("CONFIRMATION_REQUIRED"))
        status_messages = [
            str(event.get("value", {}).get("message", ""))
            for event in events
            if event.get("type") == "CUSTOM" and event.get("name") == "momcozy.agent.status"
        ]
        self.assertTrue(status_messages)
        self.assertFalse(any("support_ticket_draft_create" in message for message in status_messages))
        self.assertFalse(any(message.startswith("Tool ") for message in status_messages))

        artifact = next(event for event in events if event.get("type") == "ARTIFACT_CREATED")
        self.assertEqual(artifact["artifact_type"], "support_ticket")
        confirmation = next(event for event in events if event.get("type") == "CONFIRMATION_REQUIRED")
        self.assertEqual(confirmation["title"], "请确认售后工单")


class _FakeClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = _FakeResponses(responses)


class _FakeResponses:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = list(responses)

    def create(self, **request: object) -> dict[str, object]:
        _ = request
        if not self._responses:
            return {"id": "resp-empty", "output": []}
        return self._responses.pop(0)


if __name__ == "__main__":
    unittest.main()
