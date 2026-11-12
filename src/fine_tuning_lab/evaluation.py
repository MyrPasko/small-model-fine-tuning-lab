from __future__ import annotations

from dataclasses import dataclass

from fine_tuning_lab.toolace import (
    CanonicalTarget,
    DecisionClass,
    DecisionPoint,
    JsonValue,
    ToolACEFormatError,
    ToolCall,
    ToolSchema,
    parse_target,
)


@dataclass(frozen=True)
class Prediction:
    decision_id: str
    output: str
    latency_seconds: float = 0.0
    prompt_tokens: int = 0
    generation_tokens: int = 0
    peak_memory_gb: float = 0.0
    finish_reason: str | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "decision_id": self.decision_id,
            "finish_reason": self.finish_reason,
            "generation_tokens": self.generation_tokens,
            "latency_seconds": self.latency_seconds,
            "output": self.output,
            "peak_memory_gb": self.peak_memory_gb,
            "prompt_tokens": self.prompt_tokens,
        }


@dataclass(frozen=True)
class EvaluationReport:
    counts: dict[str, int]
    metrics: dict[str, float]
    operational: dict[str, JsonValue]
    failures: tuple[dict[str, JsonValue], ...]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "counts": {key: value for key, value in self.counts.items()},
            "failures": list(self.failures),
            "metrics": {key: value for key, value in self.metrics.items()},
            "operational": self.operational,
            "schema_version": 1,
        }


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _same_value(first: JsonValue, second: JsonValue) -> bool:
    if type(first) is not type(second):
        return False
    return first == second


def _tool_names(target: CanonicalTarget) -> tuple[str, ...]:
    return tuple(call.name for call in target.calls)


def _argument_evidence(
    gold: CanonicalTarget, predicted: CanonicalTarget
) -> tuple[int, int, int, int, int]:
    predicted_keys = 0
    gold_keys = 0
    matching_keys = 0
    gold_values = 0
    matching_values = 0
    for gold_call, predicted_call in zip(gold.calls, predicted.calls, strict=False):
        if gold_call.name != predicted_call.name:
            gold_keys += len(gold_call.arguments)
            predicted_keys += len(predicted_call.arguments)
            gold_values += len(gold_call.arguments)
            continue
        expected = set(gold_call.arguments)
        actual = set(predicted_call.arguments)
        gold_keys += len(expected)
        predicted_keys += len(actual)
        matching_keys += len(expected & actual)
        gold_values += len(expected)
        matching_values += sum(
            _same_value(gold_call.arguments[key], predicted_call.arguments[key])
            for key in expected & actual
        )
    if len(gold.calls) > len(predicted.calls):
        for call in gold.calls[len(predicted.calls) :]:
            gold_keys += len(call.arguments)
            gold_values += len(call.arguments)
    if len(predicted.calls) > len(gold.calls):
        for call in predicted.calls[len(gold.calls) :]:
            predicted_keys += len(call.arguments)
    return predicted_keys, gold_keys, matching_keys, gold_values, matching_values


def _matches_type(value: JsonValue, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "null":
        return value is None
    return True


def _mock_call_valid(call: ToolCall, schemas: tuple[ToolSchema, ...]) -> bool:
    schema_by_name = {schema.name: schema for schema in schemas}
    schema = schema_by_name.get(call.name)
    if schema is None:
        return False
    raw_properties = schema.parameters.get("properties", {})
    raw_required = schema.parameters.get("required", [])
    if not isinstance(raw_properties, dict) or not isinstance(raw_required, list):
        return False
    properties = raw_properties
    required = {item for item in raw_required if isinstance(item, str)}
    argument_keys = set(call.arguments)
    if not required <= argument_keys or not argument_keys <= set(properties):
        return False
    for key, value in call.arguments.items():
        definition = properties[key]
        if isinstance(definition, dict):
            expected_type = definition.get("type")
            if isinstance(expected_type, str) and not _matches_type(
                value, expected_type
            ):
                return False
    return True


def _mock_execution_valid(
    target: CanonicalTarget, schemas: tuple[ToolSchema, ...]
) -> bool:
    return all(_mock_call_valid(call, schemas) for call in target.calls)


def evaluate_predictions(
    decisions: dict[str, DecisionPoint], predictions: tuple[Prediction, ...]
) -> EvaluationReport:
    seen: set[str] = set()
    for prediction in predictions:
        if prediction.decision_id in seen:
            raise ValueError(f"duplicate prediction {prediction.decision_id}")
        if prediction.decision_id not in decisions:
            raise ValueError(f"unknown decision {prediction.decision_id}")
        seen.add(prediction.decision_id)

    total = len(predictions)
    parsed = 0
    exact = 0
    tool_exact = 0
    mock_pass = 0
    multi_total = 0
    multi_exact = 0
    predicted_keys = 0
    gold_keys = 0
    matching_keys = 0
    gold_values = 0
    matching_values = 0
    no_call_tp = 0
    no_call_fp = 0
    no_call_fn = 0
    failures: list[dict[str, JsonValue]] = []

    for prediction in predictions:
        decision = decisions[prediction.decision_id]
        predicted_target: CanonicalTarget | None = None
        parse_reason: str | None = None
        try:
            predicted_target = parse_target(prediction.output, decision.schemas)
        except ToolACEFormatError as error:
            parse_reason = error.reason
        else:
            parsed += 1

        if predicted_target is None:
            if decision.decision_class == DecisionClass.NO_CALL:
                no_call_fn += 1
            failures.append(
                {
                    "decision_id": decision.id,
                    "gold_class": decision.decision_class.value,
                    "reason": parse_reason or "parse_error",
                }
            )
            continue

        is_exact = predicted_target.to_dict() == decision.target.to_dict()
        exact += int(is_exact)
        names_exact = _tool_names(predicted_target) == _tool_names(decision.target)
        tool_exact += int(names_exact)
        mock_pass += int(_mock_execution_valid(predicted_target, decision.schemas))
        if decision.decision_class == DecisionClass.MULTI_CALL:
            multi_total += 1
            multi_exact += int(is_exact)

        evidence = _argument_evidence(decision.target, predicted_target)
        predicted_keys += evidence[0]
        gold_keys += evidence[1]
        matching_keys += evidence[2]
        gold_values += evidence[3]
        matching_values += evidence[4]

        gold_no_call = decision.decision_class == DecisionClass.NO_CALL
        predicted_no_call = predicted_target.decision_class == DecisionClass.NO_CALL
        no_call_tp += int(gold_no_call and predicted_no_call)
        no_call_fp += int(not gold_no_call and predicted_no_call)
        no_call_fn += int(gold_no_call and not predicted_no_call)

        if not is_exact:
            failures.append(
                {
                    "decision_id": decision.id,
                    "gold_class": decision.decision_class.value,
                    "predicted_class": predicted_target.decision_class.value,
                    "reason": "structural_mismatch",
                }
            )

    argument_precision = _safe_div(matching_keys, predicted_keys)
    argument_recall = _safe_div(matching_keys, gold_keys)
    no_call_precision = _safe_div(no_call_tp, no_call_tp + no_call_fp)
    no_call_recall = _safe_div(no_call_tp, no_call_tp + no_call_fn)
    metrics = {
        "argument_key_f1": _f1(argument_precision, argument_recall),
        "argument_key_precision": argument_precision,
        "argument_key_recall": argument_recall,
        "exact_call_sequence_rate": _safe_div(exact, total),
        "mock_execution_pass_rate": _safe_div(mock_pass, total),
        "multi_call_exact_rate": _safe_div(multi_exact, multi_total),
        "no_call_f1": _f1(no_call_precision, no_call_recall),
        "no_call_precision": no_call_precision,
        "no_call_recall": no_call_recall,
        "parseable_output_rate": _safe_div(parsed, total),
        "tool_selection_accuracy": _safe_div(tool_exact, total),
        "typed_argument_value_accuracy": _safe_div(matching_values, gold_values),
    }
    latencies = sorted(prediction.latency_seconds for prediction in predictions)
    p95_index = max(0, min(len(latencies) - 1, int(len(latencies) * 0.95)))
    operational: dict[str, JsonValue] = {
        "generation_tokens": sum(item.generation_tokens for item in predictions),
        "latency_mean_seconds": (sum(latencies) / len(latencies) if latencies else 0.0),
        "latency_p95_seconds": latencies[p95_index] if latencies else 0.0,
        "peak_memory_gb": max(
            (item.peak_memory_gb for item in predictions), default=0.0
        ),
        "prompt_tokens": sum(item.prompt_tokens for item in predictions),
    }
    counts = {
        "evaluated": total,
        "failures": len(failures),
        "parse_errors": total - parsed,
        "parsed": parsed,
        "total": total,
    }
    return EvaluationReport(
        counts=counts,
        metrics=metrics,
        operational=operational,
        failures=tuple(failures),
    )
