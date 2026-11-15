from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fine_tuning_lab.b0 import MODEL_ID, MODEL_REVISION
from fine_tuning_lab.prepare_toolace import DATASET_ID, DATASET_REVISION
from fine_tuning_lab.toolace import (
    CanonicalTarget,
    JsonValue,
    ToolACEFormatError,
    ToolSchema,
    parse_target,
)


@dataclass(frozen=True)
class CaseEvaluation:
    parseable: bool
    exact: bool
    tool_selection_exact: bool
    parsed_target: CanonicalTarget | None
    verdict: str


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _text(record: Mapping[str, object], key: str, *, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise TypeError(f"{label}.{key} must be text")
    return value


def _json_object(value: object, *, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError(f"{label} must be a JSON object")
    return cast(dict[str, JsonValue], value)


def _load_jsonl(path: Path) -> tuple[object, ...]:
    records: list[object] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON at {path}:{line_number}") from error
    return tuple(records)


def _result_id(raw_result: object) -> str:
    result = _mapping(raw_result, label="result")
    prediction = result.get("prediction")
    if prediction is not None:
        return _text(
            _mapping(prediction, label="result.prediction"),
            "decision_id",
            label="result.prediction",
        )
    return _text(result, "decision_id", label="result")


def _index_results(results: Sequence[object]) -> dict[str, Mapping[str, object]]:
    by_id: dict[str, Mapping[str, object]] = {}
    for raw_result in results:
        decision_id = _result_id(raw_result)
        if decision_id in by_id:
            raise ValueError(f"duplicate result for {decision_id}")
        by_id[decision_id] = _mapping(raw_result, label="result")
    return by_id


def _schemas(decision: Mapping[str, object]) -> tuple[ToolSchema, ...]:
    raw_schemas = decision.get("schemas")
    if not isinstance(raw_schemas, list):
        raise TypeError("decision.schemas must be a list")
    schemas: list[ToolSchema] = []
    for index, raw_schema in enumerate(raw_schemas):
        schema = _mapping(raw_schema, label=f"decision.schemas[{index}]")
        schemas.append(
            ToolSchema(
                name=_text(schema, "name", label=f"decision.schemas[{index}]"),
                description=_text(
                    schema, "description", label=f"decision.schemas[{index}]"
                ),
                parameters=_json_object(
                    schema.get("parameters"),
                    label=f"decision.schemas[{index}].parameters",
                ),
            )
        )
    return tuple(schemas)


def _tool_names(target: CanonicalTarget) -> tuple[str, ...]:
    return tuple(call.name for call in target.calls)


def _expected_tool_names(target: Mapping[str, object]) -> tuple[str, ...]:
    raw_calls = target.get("calls")
    if not isinstance(raw_calls, list):
        raise TypeError("decision.target.calls must be a list")
    return tuple(
        _text(
            _mapping(raw_call, label="decision.target.calls[]"),
            "name",
            label="decision.target.calls[]",
        )
        for raw_call in raw_calls
    )


def _evaluate(
    decision: Mapping[str, object], result: Mapping[str, object]
) -> CaseEvaluation:
    status = _text(result, "status", label="result")
    if status != "completed":
        return CaseEvaluation(
            parseable=False,
            exact=False,
            tool_selection_exact=False,
            parsed_target=None,
            verdict=f"NOT SCORED — generation status: {status}",
        )

    prediction = _mapping(result.get("prediction"), label="result.prediction")
    output = _text(prediction, "output", label="result.prediction")
    schemas = _schemas(decision)
    try:
        parsed = parse_target(output, schemas)
    except ToolACEFormatError as error:
        detail = f" ({error.detail})" if error.detail else ""
        return CaseEvaluation(
            parseable=False,
            exact=False,
            tool_selection_exact=False,
            parsed_target=None,
            verdict=(f"FAIL — відповідь не вдалося розібрати: {error.reason}{detail}"),
        )

    expected = _json_object(decision.get("target"), label="decision.target")
    exact = parsed.to_dict() == expected
    tool_selection_exact = _tool_names(parsed) == _expected_tool_names(expected)
    if exact:
        verdict = "PASS — повний збіг"
    elif not tool_selection_exact:
        verdict = "FAIL — неправильний інструмент, кількість викликів або порядок"
    else:
        verdict = "FAIL — інструмент вибрано правильно, але аргументи не збігаються"
    return CaseEvaluation(
        parseable=True,
        exact=exact,
        tool_selection_exact=tool_selection_exact,
        parsed_target=parsed,
        verdict=verdict,
    )


def _code_block(value: str, language: str = "text") -> str:
    normalized = "\n".join(line.rstrip() for line in value.splitlines())
    longest_run = max((len(run) for run in re.findall(r"`+", normalized)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}{language}\n{normalized}\n{fence}"


def _yes_no(value: bool) -> str:
    return "так" if value else "ні"


def _task_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "завдання"
    if count % 10 in {2, 3, 4} and count % 100 not in {12, 13, 14}:
        return "завдання"
    return "завдань"


def _format_context(decision: Mapping[str, object]) -> str:
    raw_context = decision.get("context")
    if not isinstance(raw_context, list):
        raise TypeError("decision.context must be a list")
    parts: list[str] = []
    for index, raw_message in enumerate(raw_context):
        message = _mapping(raw_message, label=f"decision.context[{index}]")
        role = _text(message, "role", label=f"decision.context[{index}]").upper()
        content = _text(message, "content", label=f"decision.context[{index}]")
        parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def _format_schema(schema: ToolSchema) -> str:
    properties = schema.parameters.get("properties", {})
    required = schema.parameters.get("required", [])
    property_map = properties if isinstance(properties, dict) else {}
    required_names = (
        {value for value in required if isinstance(value, str)}
        if isinstance(required, list)
        else set()
    )
    parameters: list[str] = []
    for name, raw_definition in property_map.items():
        definition = raw_definition if isinstance(raw_definition, dict) else {}
        parameter_type = definition.get("type", "unknown")
        required_label = ", required" if name in required_names else ""
        parameters.append(f"{name}: {parameter_type}{required_label}")
    signature = f"{schema.name}({', '.join(parameters)})"
    description = " ".join(schema.description.split())
    return f"- `{signature}` — {description}" if description else f"- `{signature}`"


def _prediction_output(result: Mapping[str, object]) -> str:
    if result.get("prediction") is None:
        error = result.get("error")
        return str(error) if error is not None else "No model output."
    prediction = _mapping(result.get("prediction"), label="result.prediction")
    return _text(prediction, "output", label="result.prediction")


def _render_case(
    index: int,
    decision: Mapping[str, object],
    result: Mapping[str, object],
    evaluation: CaseEvaluation,
) -> str:
    decision_id = _text(decision, "id", label="decision")
    split = _text(result, "split", label="result")
    decision_class = _text(decision, "decision_class", label="decision")
    expected = _json_object(decision.get("target"), label="decision.target")
    raw_target = _text(decision, "raw_target", label="decision")
    parsed = (
        json.dumps(evaluation.parsed_target.to_dict(), ensure_ascii=False, indent=2)
        if evaluation.parsed_target is not None
        else "Not available because parsing failed."
    )
    schema_lines = "\n".join(_format_schema(schema) for schema in _schemas(decision))
    icon = "✅" if evaluation.exact else "❌"
    return "\n".join(
        (
            f"## Завдання {index:03d} — {icon} {evaluation.verdict}",
            "",
            f"- **Decision ID:** `{decision_id}`",
            f"- **Split:** `{split}`",
            f"- **Клас:** `{decision_class}`",
            "",
            "### Контекст, який отримала модель",
            "",
            _code_block(_format_context(decision)),
            "",
            "### Доступні інструменти",
            "",
            schema_lines,
            "",
            "### Еталонне routing-рішення",
            "",
            _code_block(json.dumps(expected, ensure_ascii=False, indent=2), "json"),
            "",
            "Оригінальна відповідь ToolACE:",
            "",
            _code_block(raw_target),
            "",
            "### Фактична відповідь базової моделі",
            "",
            _code_block(_prediction_output(result)),
            "",
            "Рішення після парсингу:",
            "",
            _code_block(parsed, "json"),
            "",
            "### Вердикт",
            "",
            f"- **Результат:** {evaluation.verdict}",
            f"- **Відповідь можна розібрати:** {_yes_no(evaluation.parseable)}",
            f"- **Вибір інструментів збігається:** {_yes_no(evaluation.tool_selection_exact)}",
            f"- **Повна структура збігається:** {_yes_no(evaluation.exact)}",
            "",
        )
    )


def build_exam_book(decisions: Sequence[object], results: Sequence[object]) -> str:
    result_by_id = _index_results(results)
    indexed_decisions: list[Mapping[str, object]] = []
    seen_decisions: set[str] = set()
    for raw_decision in decisions:
        decision = _mapping(raw_decision, label="decision")
        decision_id = _text(decision, "id", label="decision")
        if decision_id in seen_decisions:
            raise ValueError(f"duplicate decision {decision_id}")
        seen_decisions.add(decision_id)
        if decision_id not in result_by_id:
            raise ValueError(f"missing result for {decision_id}")
        indexed_decisions.append(decision)
    extra_results = set(result_by_id) - seen_decisions
    if extra_results:
        raise ValueError(f"result without decision: {min(extra_results)}")

    evaluated = [
        (decision, result_by_id[_text(decision, "id", label="decision")])
        for decision in indexed_decisions
    ]
    evaluations = [_evaluate(decision, result) for decision, result in evaluated]
    total = len(evaluations)
    exact = sum(item.exact for item in evaluations)
    parsed = sum(item.parseable for item in evaluations)
    tool_exact = sum(item.tool_selection_exact for item in evaluations)
    standard = sum(
        _text(result, "split", label="result") == "standard" for _, result in evaluated
    )
    strict = total - standard

    header = f"""# EXP-001 — B0 Exam Book

Це видиме представлення базового екзамену **до fine-tuning**. Воно показує не загальну «якість моделі», а вузьку здатність: отримавши запит користувача та набір tool schemas, вибрати потрібні інструменти, сформувати аргументи або не викликати нічого.

## Карта експерименту

```mermaid
flowchart TD
    A["ToolACE data.json<br/>11 300 діалогів"] -->|prepare_toolace.py| B["Канонічні decision points<br/>11 519 прийнято"]
    B --> C["Train<br/>11 382"]
    B --> D["Standard test<br/>64"]
    B --> E["Schema-disjoint test<br/>64"]
    D --> F["B0: базова Qwen3-1.7B<br/>без навчання"]
    E --> F
    F --> G[128 відповідей моделі]
    G -->|evaluation.py| H[Exam Book + B0 report]
    C -. майбутній S1 / E1 .-> I["QLoRA fine-tuning<br/>ще не запускався"]
    I -. той самий екзамен .-> H
```

## Що де лежить

- [`README.md`](../../README.md) — дослідницьке питання та межі EXP-001.
- [`prepare_toolace.py`](../../src/fine_tuning_lab/prepare_toolace.py) — перевіряє ToolACE, перетворює діалоги на decision points і створює splits.
- [`splits.py`](../../src/fine_tuning_lab/splits.py) — формує train, standard test і schema-disjoint test.
- [`b0.py`](../../src/fine_tuning_lab/b0.py) — збирає prompt і запускає базову модель на 128 завданнях.
- [`evaluation.py`](../../src/fine_tuning_lab/evaluation.py) — парсить відповіді та рахує результати.
- [`exam_book.py`](../../src/fine_tuning_lab/exam_book.py) — генерує цей читабельний документ.
- [`b0_manifest.json`](b0_manifest.json) — фіксує модель, dataset revision, кількість і хеш екзаменаційних завдань.
- [`b0_report.json`](b0_report.json) — компактний машинний підсумок B0.

Повні машинні джерела залишаються локальними, але більше не є єдиним способом побачити екзамен:

- `~/.cache/small-model-fine-tuning-lab/exp-001/toolace/b0_decisions.jsonl` — 128 вхідних завдань;
- `~/.cache/small-model-fine-tuning-lab/exp-001/b0/b0_results.jsonl` — 128 фактичних відповідей моделі.

## Як оцінюється одне завдання

Для кожного завдання модель отримує однакову інструкцію: вибрати потрібні інструменти, повернути лише bracket-style виклики `[tool_name(argument=value)]` у правильному порядку або коротко пояснити, що жоден інструмент не підходить. Thinking вимкнено префілом `<think></think>`, генерація детермінована (`temperature=0`, максимум 256 нових токенів).

1. Модель отримує цю інструкцію, попередній контекст діалогу та список доступних tool schemas.
2. Вона повертає bracket-style виклик або звичайний текст, якщо інструмент не потрібен.
3. Парсер перетворює відповідь на канонічне routing-рішення `{{"calls": [...]}}`.
4. Повний збіг означає, що кількість, порядок, назви інструментів і всі аргументи збігаються з еталоном.

## Підсумок

- **Усього:** {total} {_task_word(total)}
- **Standard test:** {standard}
- **Schema-disjoint test:** {strict}
- **Відповідь вдалося розібрати:** {parsed}/{total}
- **Правильний вибір інструментів:** {tool_exact}/{total}
- **Повний збіг:** {exact}/{total}

Нижче наведені **всі {total} завдань**, а не вибрана демонстраційна підмножина.

---
"""
    cases = "\n".join(
        _render_case(index, decision, result, evaluation)
        for index, ((decision, result), evaluation) in enumerate(
            zip(evaluated, evaluations, strict=True), 1
        )
    )
    return header + "\n" + cases


def write_exam_book(
    decisions_path: Path, results_path: Path, output_path: Path
) -> None:
    rendered = build_exam_book(_load_jsonl(decisions_path), _load_jsonl(results_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            f"Render a human-readable {DATASET_ID} B0 exam book for {MODEL_ID} "
            f"(dataset {DATASET_REVISION}, model {MODEL_REVISION})."
        )
    )
    parser.add_argument("decisions", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    write_exam_book(arguments.decisions, arguments.results, arguments.output)


if __name__ == "__main__":
    main()
