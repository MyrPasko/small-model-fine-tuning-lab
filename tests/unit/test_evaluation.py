import json
import unittest

from fine_tuning_lab.evaluation import Prediction, evaluate_predictions
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
    decision = transform_rows(rows, source_revision=f"revision-{row_index}").accepted[0]
    return decision


class TestEvaluation(unittest.TestCase):
    def test_exact_predictions_score_one_for_structural_metrics(self) -> None:
        call = _decision("[lookup(value=7)]", row_index=0)
        no_call = _decision("No tool is required.", row_index=1)
        predictions = (
            Prediction(decision_id=call.id, output="[lookup(value=7)]"),
            Prediction(decision_id=no_call.id, output="No tool is required."),
        )

        report = evaluate_predictions({call.id: call, no_call.id: no_call}, predictions)
        metrics = report.metrics

        self.assertEqual(metrics["parseable_output_rate"], 1.0)
        self.assertEqual(metrics["exact_call_sequence_rate"], 1.0)
        self.assertEqual(metrics["tool_selection_accuracy"], 1.0)
        self.assertEqual(metrics["typed_argument_value_accuracy"], 1.0)
        self.assertEqual(metrics["no_call_f1"], 1.0)

    def test_malformed_output_is_counted_and_never_silently_dropped(self) -> None:
        call = _decision("[lookup(value=7)]", row_index=0)
        predictions = (Prediction(decision_id=call.id, output="[lookup(value=]"),)

        report = evaluate_predictions({call.id: call}, predictions)
        self.assertEqual(report.counts["total"], 1)
        self.assertEqual(report.counts["parse_errors"], 1)
        self.assertEqual(report.metrics["parseable_output_rate"], 0.0)
        self.assertEqual(report.metrics["exact_call_sequence_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
