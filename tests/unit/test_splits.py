import json
import unittest

from fine_tuning_lab.splits import (
    build_split_plan,
    schema_similarity,
    validate_split_plan,
)
from fine_tuning_lab.toolace import DecisionClass, DecisionPoint, transform_rows


def _schema(name: str, parameter: str) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Use {name} for {parameter}",
        "parameters": {
            "type": "object",
            "properties": {parameter: {"type": "string"}},
            "required": [parameter],
        },
    }


def _decisions() -> tuple[DecisionPoint, ...]:
    rows: list[object] = []
    for index in range(18):
        schema = _schema(f"tool_{index}", f"field_{index}")
        if index % 3 == 0:
            target = "No tool is required."
        elif index % 3 == 1:
            target = f'[tool_{index}(field_{index}="value-{index}")]'
        else:
            target = (
                f'[tool_{index}(field_{index}="first-{index}"), '
                f'tool_{index}(field_{index}="second-{index}")]'
            )
        rows.append(
            {
                "system": (
                    "Here is a list of functions in JSON format that you can invoke:\n"
                    + json.dumps([schema])
                ),
                "conversations": [
                    {"from": "user", "value": f"unique prompt {index}"},
                    {"from": "assistant", "value": target},
                ],
            }
        )
    return transform_rows(rows, source_revision="revision-1").accepted


class TestToolACESplits(unittest.TestCase):
    def test_split_is_deterministic_bounded_and_conversation_disjoint(self) -> None:
        decisions = _decisions()

        first = build_split_plan(
            decisions,
            seed=42,
            standard_limit=6,
            strict_limit=6,
            near_schema_threshold=0.85,
        )
        second = build_split_plan(
            decisions,
            seed=42,
            standard_limit=6,
            strict_limit=6,
            near_schema_threshold=0.85,
        )

        self.assertEqual(first.manifest_hash, second.manifest_hash)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertLessEqual(len(first.standard_ids), 6)
        self.assertLessEqual(len(first.strict_ids), 6)

        by_id = {decision.id: decision for decision in decisions}
        split_rows = {
            name: {by_id[decision_id].row_index for decision_id in ids}
            for name, ids in {
                "train": first.train_ids,
                "standard": first.standard_ids,
                "strict": first.strict_ids,
            }.items()
        }
        self.assertTrue(split_rows["train"].isdisjoint(split_rows["standard"]))
        self.assertTrue(split_rows["train"].isdisjoint(split_rows["strict"]))
        self.assertTrue(split_rows["standard"].isdisjoint(split_rows["strict"]))
        self.assertEqual(
            validate_split_plan(first, decisions)["hard_leakage_violation_count"],
            0,
        )

    def test_strict_schemas_and_test_prompts_do_not_leak_into_train(self) -> None:
        decisions = _decisions()
        plan = build_split_plan(
            decisions,
            seed=42,
            standard_limit=4,
            strict_limit=4,
            near_schema_threshold=0.85,
        )
        by_id = {decision.id: decision for decision in decisions}
        train = [by_id[decision_id] for decision_id in plan.train_ids]
        strict = [by_id[decision_id] for decision_id in plan.strict_ids]
        tests = [
            by_id[decision_id] for decision_id in (*plan.standard_ids, *plan.strict_ids)
        ]

        self.assertTrue(
            {decision.prompt_fingerprint for decision in train}.isdisjoint(
                {decision.prompt_fingerprint for decision in tests}
            )
        )
        for strict_decision in strict:
            for train_decision in train:
                self.assertLess(
                    schema_similarity(strict_decision, train_decision),
                    0.85,
                )

    def test_bounded_selection_preserves_available_decision_classes(self) -> None:
        decisions = _decisions()
        plan = build_split_plan(
            decisions,
            seed=42,
            standard_limit=6,
            strict_limit=6,
            near_schema_threshold=0.85,
        )
        by_id = {decision.id: decision for decision in decisions}

        for ids in (plan.standard_ids, plan.strict_ids):
            classes = {by_id[decision_id].decision_class for decision_id in ids}
            self.assertEqual(
                classes,
                {
                    DecisionClass.NO_CALL,
                    DecisionClass.SINGLE_CALL,
                    DecisionClass.MULTI_CALL,
                },
            )


if __name__ == "__main__":
    unittest.main()
