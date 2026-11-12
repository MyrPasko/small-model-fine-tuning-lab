import json
import unittest
from typing import cast

from fine_tuning_lab.toolace import (
    DecisionClass,
    JsonValue,
    ToolACEFormatError,
    canonical_json,
    parse_target,
    parse_tool_schemas,
    transform_rows,
)


def _system(*schemas: dict[str, object]) -> str:
    return (
        "You are an expert in composing functions.\n"
        "Here is a list of functions in JSON format that you can invoke:\n"
        + json.dumps(list(schemas))
    )


def _schema(name: str, *, value_type: str = "str") -> dict[str, object]:
    return {
        "name": name,
        "description": f"Call {name}",
        "parameters": {
            "type": "dict",
            "properties": {"value": {"type": value_type, "description": "A value"}},
            "required": ["value"],
        },
    }


class TestToolACESchemaParsing(unittest.TestCase):
    def test_json_schemas_are_normalized_to_json_schema_types(self) -> None:
        schemas = parse_tool_schemas(_system(_schema("lookup", value_type="int")))

        self.assertEqual(len(schemas), 1)
        self.assertEqual(schemas[0].name, "lookup")
        self.assertEqual(schemas[0].parameters["type"], "object")
        properties = cast(dict[str, JsonValue], schemas[0].parameters["properties"])
        value_schema = cast(dict[str, JsonValue], properties["value"])
        self.assertEqual(value_schema["type"], "integer")

    def test_schema_fingerprint_is_independent_of_source_key_order(self) -> None:
        first = parse_tool_schemas(_system(_schema("lookup")))[0]
        reordered = {
            "parameters": _schema("lookup")["parameters"],
            "description": "Call lookup",
            "name": "lookup",
        }
        second = parse_tool_schemas(_system(reordered))[0]

        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(
            canonical_json(first.to_dict()), canonical_json(second.to_dict())
        )

    def test_non_json_schema_formats_are_rejected_without_repair(self) -> None:
        with self.assertRaisesRegex(ToolACEFormatError, "unsupported_schema_format"):
            parse_tool_schemas("Here are the tools you can use:\n<tool>lookup</tool>")


class TestToolACETargetParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.schemas = parse_tool_schemas(
            _system(_schema("lookup", value_type="int"), _schema("save"))
        )

    def test_single_call_becomes_canonical_ir(self) -> None:
        target = parse_target("[lookup(value=7)]", self.schemas)

        self.assertEqual(target.decision_class, DecisionClass.SINGLE_CALL)
        self.assertEqual(
            target.to_dict(),
            {"calls": [{"name": "lookup", "arguments": {"value": 7}}]},
        )

    def test_multiple_calls_and_safe_python_literals_are_supported(self) -> None:
        target = parse_target(
            '[lookup(value=True), save(value={"items": [1, 2]})]',
            self.schemas,
        )

        self.assertEqual(target.decision_class, DecisionClass.MULTI_CALL)
        self.assertEqual(target.calls[0].arguments["value"], True)
        self.assertEqual(target.calls[1].arguments["value"], {"items": [1, 2]})

    def test_natural_language_target_is_a_no_call_decision(self) -> None:
        target = parse_target(
            "No available tool can answer this request.", self.schemas
        )

        self.assertEqual(target.decision_class, DecisionClass.NO_CALL)
        self.assertEqual(target.to_dict(), {"calls": []})

    def test_empty_malformed_and_unknown_calls_are_rejected(self) -> None:
        cases = {
            "": "empty_target",
            "[lookup(value=]": "malformed_call_target",
            "[missing(value=1)]": "unknown_tool",
        }
        for value, reason in cases.items():
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ToolACEFormatError, reason),
            ):
                parse_target(value, self.schemas)


class TestToolACETransformation(unittest.TestCase):
    def test_only_assistant_turns_immediately_after_user_are_decisions(self) -> None:
        rows: list[object] = [
            {
                "system": _system(_schema("lookup", value_type="int")),
                "conversations": [
                    {"from": "user", "value": "Find seven"},
                    {"from": "assistant", "value": "[lookup(value=7)]"},
                    {"from": "tool", "value": "seven"},
                    {"from": "assistant", "value": "The result is seven."},
                    {"from": "user", "value": "Can you also explain it?"},
                    {"from": "assistant", "value": "No tool is needed."},
                ],
            }
        ]

        result = transform_rows(rows, source_revision="revision-1")

        self.assertEqual(len(result.accepted), 2)
        self.assertEqual(
            [decision.decision_class for decision in result.accepted],
            [DecisionClass.SINGLE_CALL, DecisionClass.NO_CALL],
        )
        self.assertEqual(result.report.candidate_decisions, 2)
        self.assertEqual(result.report.ineligible_assistant_turns, 1)
        self.assertEqual(result.report.row_status_counts, {"accepted": 1})

    def test_every_candidate_gets_an_accepted_or_rejected_terminal_status(self) -> None:
        rows: list[object] = [
            {
                "system": _system(_schema("lookup")),
                "conversations": [
                    {"from": "user", "value": "Valid"},
                    {"from": "assistant", "value": '[lookup(value="x")]'},
                    {"from": "user", "value": "Invalid"},
                    {"from": "assistant", "value": ""},
                ],
            },
            {
                "system": "Here are the tools you can use: <xml />",
                "conversations": [
                    {"from": "user", "value": "Unsupported schema"},
                    {"from": "assistant", "value": "No tool"},
                ],
            },
        ]

        result = transform_rows(rows, source_revision="revision-1")

        self.assertEqual(result.report.rows_total, 2)
        self.assertEqual(result.report.candidate_decisions, 3)
        self.assertEqual(result.report.accepted_decisions, 1)
        self.assertEqual(result.report.rejected_decisions, 2)
        self.assertEqual(len(result.accepted) + len(result.rejected), 3)
        self.assertEqual(
            result.report.rejection_reason_counts,
            {"empty_target": 1, "unsupported_schema_format": 1},
        )
        self.assertEqual(
            result.report.row_status_counts,
            {"partial": 1, "rejected": 1},
        )


if __name__ == "__main__":
    unittest.main()
