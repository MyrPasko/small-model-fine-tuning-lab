import json
import unittest

from fine_tuning_lab.exam_book import build_exam_book
from fine_tuning_lab.toolace import DecisionPoint, transform_rows


def _decision(target: str, *, row_index: int) -> DecisionPoint:
    schema = {
        "name": "lookup",
        "description": "Look up a value",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
            "required": ["value"],
        },
    }
    rows: list[object] = [
        {
            "system": (
                "Here is a list of functions in JSON format that you can invoke:\n"
                + json.dumps([schema])
            ),
            "conversations": [
                {"from": "user", "value": f"request {row_index}"},
                {"from": "assistant", "value": target},
            ],
        }
    ]
    return transform_rows(rows, source_revision=f"revision-{row_index}").accepted[0]


def _result(decision: DecisionPoint, output: str, *, split: str = "standard") -> object:
    return {
        "prediction": {
            "decision_id": decision.id,
            "finish_reason": "stop",
            "generation_tokens": 1,
            "latency_seconds": 0.1,
            "output": output,
            "peak_memory_gb": 0.2,
            "prompt_tokens": 10,
        },
        "split": split,
        "status": "completed",
    }


class TestExamBook(unittest.TestCase):
    def test_renders_every_case_with_evidence_and_verdict(self) -> None:
        exact = _decision("[lookup(value=7)]", row_index=0)
        malformed = _decision("[lookup(value=8)]", row_index=1)

        rendered = build_exam_book(
            (exact.to_dict(), malformed.to_dict()),
            (
                _result(exact, "[lookup(value=7)]  "),
                _result(malformed, "[lookup(value=]", split="strict_schema_disjoint"),
            ),
        )

        self.assertIn("# EXP-001 — B0 Exam Book", rendered)
        self.assertIn("2 завдання", rendered)
        self.assertIn("request 0", rendered)
        self.assertIn("`lookup(value: integer, required)`", rendered)
        self.assertIn('"value": 7', rendered)
        self.assertIn("[lookup(value=7)]", rendered)
        self.assertIn("PASS — повний збіг", rendered)
        self.assertIn("FAIL — відповідь не вдалося розібрати", rendered)
        self.assertEqual(rendered.count("## Завдання "), 2)
        self.assertFalse(any(line.endswith(" ") for line in rendered.splitlines()))

    def test_rejects_missing_or_duplicate_results(self) -> None:
        decision = _decision("[lookup(value=7)]", row_index=0)

        with self.assertRaisesRegex(ValueError, "missing result"):
            build_exam_book((decision.to_dict(),), ())

        result = _result(decision, "[lookup(value=7)]")
        with self.assertRaisesRegex(ValueError, "duplicate result"):
            build_exam_book((decision.to_dict(),), (result, result))


if __name__ == "__main__":
    unittest.main()
