import json
import unittest
from typing import cast

from fine_tuning_lab.b0 import (
    NON_THINKING_PREFILL,
    build_b0_manifest,
    build_messages,
)
from fine_tuning_lab.splits import build_split_plan
from fine_tuning_lab.toolace import DecisionPoint, JsonValue, transform_rows


def _decisions() -> tuple[DecisionPoint, ...]:
    rows: list[object] = []
    for index in range(6):
        schema = {
            "name": f"tool_{index}",
            "description": f"Tool {index}",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        }
        rows.append(
            {
                "system": (
                    "Here is a list of functions in JSON format that you can invoke:\n"
                    + json.dumps([schema])
                ),
                "conversations": [
                    {"from": "user", "value": f"request {index}"},
                    {"from": "assistant", "value": f"[tool_{index}(value={index})]"},
                ],
            }
        )
    return transform_rows(rows, source_revision="revision-1").accepted


class TestB0Contract(unittest.TestCase):
    def test_messages_use_canonical_schemas_and_verified_non_thinking_prefill(
        self,
    ) -> None:
        decision = _decisions()[0]

        messages = build_messages(decision)

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn('"name":"tool_0"', messages[0]["content"])
        self.assertEqual(messages[-2], {"role": "user", "content": "request 0"})
        self.assertEqual(
            messages[-1], {"role": "assistant", "content": NON_THINKING_PREFILL}
        )

    def test_manifest_freezes_exact_items_and_is_deterministic(self) -> None:
        decisions = _decisions()
        plan = build_split_plan(
            decisions,
            seed=42,
            standard_limit=3,
            strict_limit=3,
            near_schema_threshold=0.85,
        )
        by_id = {decision.id: decision for decision in decisions}

        first = build_b0_manifest(plan, by_id)
        second = build_b0_manifest(plan, by_id)

        self.assertEqual(first, second)
        self.assertEqual(len(cast(list[JsonValue], first["evaluation_items"])), 6)
        self.assertEqual(len(cast(str, first["manifest_sha256"])), 64)


if __name__ == "__main__":
    unittest.main()
