from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

SCHEMA_MARKER = "Here is a list of functions in JSON format that you can invoke:"

_TYPE_ALIASES = {
    "any": "object",
    "bool": "boolean",
    "boolean": "boolean",
    "dict": "object",
    "float": "number",
    "int": "integer",
    "integer": "integer",
    "list": "array",
    "none": "null",
    "null": "null",
    "number": "number",
    "object": "object",
    "str": "string",
    "string": "string",
}


class ToolACEFormatError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        suffix = f": {detail}" if detail else ""
        super().__init__(f"{reason}{suffix}")


class DecisionClass(StrEnum):
    NO_CALL = "no_call"
    SINGLE_CALL = "single_call"
    MULTI_CALL = "multi_call"


def canonical_json(value: JsonValue) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_json(value: object, *, key: str | None = None) -> JsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        if key == "type" and isinstance(value, str):
            return _TYPE_ALIASES.get(value.lower(), value.lower())
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ToolACEFormatError("unsupported_literal", "non-finite number")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                raise ToolACEFormatError("unsupported_literal", "non-string key")
            normalized[raw_key] = _normalize_json(raw_value, key=raw_key)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item) for item in value]
    raise ToolACEFormatError(
        "unsupported_literal", f"unsupported value type {type(value).__name__}"
    )


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, JsonValue]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "description": self.description,
            "name": self.name,
            "parameters": self.parameters,
        }

    @property
    def fingerprint(self) -> str:
        return _sha256_text(canonical_json(self.to_dict()))


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, JsonValue]

    def to_dict(self) -> dict[str, JsonValue]:
        return {"arguments": self.arguments, "name": self.name}


@dataclass(frozen=True)
class CanonicalTarget:
    calls: tuple[ToolCall, ...]

    @property
    def decision_class(self) -> DecisionClass:
        if not self.calls:
            return DecisionClass.NO_CALL
        if len(self.calls) == 1:
            return DecisionClass.SINGLE_CALL
        return DecisionClass.MULTI_CALL

    def to_dict(self) -> dict[str, JsonValue]:
        return {"calls": [call.to_dict() for call in self.calls]}


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {"content": self.content, "role": self.role}


@dataclass(frozen=True)
class DecisionPoint:
    id: str
    source_revision: str
    row_index: int
    assistant_turn_index: int
    schemas: tuple[ToolSchema, ...]
    context: tuple[ChatMessage, ...]
    target: CanonicalTarget
    raw_target: str

    @property
    def decision_class(self) -> DecisionClass:
        return self.target.decision_class

    @property
    def prompt_fingerprint(self) -> str:
        prompt = self.context[-1].content.casefold()
        normalized = " ".join(prompt.split())
        return _sha256_text(normalized)

    @property
    def schema_fingerprint(self) -> str:
        payload: JsonValue = [schema.to_dict() for schema in self.schemas]
        return _sha256_text(canonical_json(payload))

    @property
    def schema_tokens(self) -> frozenset[str]:
        payload: JsonValue = [schema.to_dict() for schema in self.schemas]
        return frozenset(re.findall(r"[a-z0-9]+", canonical_json(payload).casefold()))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "assistant_turn_index": self.assistant_turn_index,
            "context": [message.to_dict() for message in self.context],
            "decision_class": self.decision_class.value,
            "id": self.id,
            "prompt_fingerprint": self.prompt_fingerprint,
            "raw_target": self.raw_target,
            "row_index": self.row_index,
            "schema_fingerprint": self.schema_fingerprint,
            "schemas": [schema.to_dict() for schema in self.schemas],
            "source_revision": self.source_revision,
            "target": self.target.to_dict(),
        }


@dataclass(frozen=True)
class RejectedDecision:
    id: str
    row_index: int
    assistant_turn_index: int
    reason: str
    detail: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "assistant_turn_index": self.assistant_turn_index,
            "detail": self.detail,
            "id": self.id,
            "reason": self.reason,
            "row_index": self.row_index,
        }


@dataclass(frozen=True)
class TransformationReport:
    rows_total: int
    candidate_decisions: int
    accepted_decisions: int
    rejected_decisions: int
    ineligible_assistant_turns: int
    row_status_counts: dict[str, int]
    decision_class_counts: dict[str, int]
    rejection_reason_counts: dict[str, int]

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "accepted_decisions": self.accepted_decisions,
            "candidate_decisions": self.candidate_decisions,
            "decision_class_counts": {
                key: value for key, value in self.decision_class_counts.items()
            },
            "ineligible_assistant_turns": self.ineligible_assistant_turns,
            "rejected_decisions": self.rejected_decisions,
            "rejection_reason_counts": {
                key: value for key, value in self.rejection_reason_counts.items()
            },
            "row_status_counts": {
                key: value for key, value in self.row_status_counts.items()
            },
            "rows_total": self.rows_total,
        }


@dataclass(frozen=True)
class TransformationResult:
    accepted: tuple[DecisionPoint, ...]
    rejected: tuple[RejectedDecision, ...]
    report: TransformationReport


def parse_tool_schemas(system: str) -> tuple[ToolSchema, ...]:
    marker_index = system.find(SCHEMA_MARKER)
    if marker_index < 0:
        raise ToolACEFormatError("unsupported_schema_format", "JSON marker not found")

    source = system[marker_index + len(SCHEMA_MARKER) :].lstrip()
    try:
        decoded, _ = json.JSONDecoder().raw_decode(source)
    except json.JSONDecodeError as error:
        raise ToolACEFormatError(
            "malformed_schema_json", f"line {error.lineno} column {error.colno}"
        ) from error

    if not isinstance(decoded, list) or not decoded:
        raise ToolACEFormatError("malformed_schema_json", "expected non-empty list")

    schemas: list[ToolSchema] = []
    names: set[str] = set()
    for index, raw_schema in enumerate(decoded):
        if not isinstance(raw_schema, Mapping):
            raise ToolACEFormatError(
                "malformed_schema_json", f"schema {index} is not an object"
            )
        name = raw_schema.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ToolACEFormatError(
                "malformed_schema_json", f"schema {index} has no name"
            )
        normalized_name = name.strip()
        if normalized_name in names:
            raise ToolACEFormatError(
                "malformed_schema_json", f"duplicate tool name {normalized_name}"
            )
        description_value = raw_schema.get("description", "")
        if not isinstance(description_value, str):
            raise ToolACEFormatError(
                "malformed_schema_json", f"schema {index} description is not text"
            )
        raw_parameters = raw_schema.get("parameters", {})
        normalized_parameters = _normalize_json(raw_parameters)
        if not isinstance(normalized_parameters, dict):
            raise ToolACEFormatError(
                "malformed_schema_json", f"schema {index} parameters are not an object"
            )
        schemas.append(
            ToolSchema(
                name=normalized_name,
                description=description_value.strip(),
                parameters=normalized_parameters,
            )
        )
        names.add(normalized_name)
    return tuple(schemas)


def _split_top_level(source: str, separator: str) -> list[str]:
    if not source.strip():
        return []
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, character in enumerate(source):
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character in "([{":
            stack.append(character)
        elif character in ")]}":
            if not stack or stack.pop() != pairs[character]:
                raise ToolACEFormatError(
                    "malformed_call_target", "unbalanced delimiters"
                )
        elif character == separator and not stack:
            parts.append(source[start:index].strip())
            start = index + 1
    if quote is not None or stack:
        raise ToolACEFormatError("malformed_call_target", "unclosed literal")
    parts.append(source[start:].strip())
    if any(not part for part in parts):
        raise ToolACEFormatError("malformed_call_target", "empty item")
    return parts


def _split_argument(argument: str) -> tuple[str, str]:
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, character in enumerate(argument):
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {'"', "'"}:
            quote = character
        elif character in "([{":
            stack.append(character)
        elif character in ")]}":
            if not stack or stack.pop() != pairs[character]:
                break
        elif character == "=" and not stack:
            return argument[:index].strip(), argument[index + 1 :].strip()
    raise ToolACEFormatError("malformed_call_target", "argument has no equals sign")


def _parse_literal(source: str) -> JsonValue:
    if not source:
        raise ToolACEFormatError("malformed_call_target", "empty argument value")
    try:
        return _normalize_json(json.loads(source))
    except (json.JSONDecodeError, ToolACEFormatError):
        pass
    if source == "True":
        return True
    if source == "False":
        return False
    if source == "None":
        return None
    try:
        literal = ast.literal_eval(source)
    except (SyntaxError, ValueError) as error:
        raise ToolACEFormatError(
            "malformed_call_target", f"unsupported literal {source[:80]}"
        ) from error
    return _normalize_json(literal)


def _parse_call(source: str, known_tools: set[str]) -> ToolCall:
    open_index = source.find("(")
    if open_index <= 0 or not source.endswith(")"):
        raise ToolACEFormatError("malformed_call_target", "expected name(arguments)")
    name = source[:open_index].strip()
    if not name:
        raise ToolACEFormatError("malformed_call_target", "blank tool name")
    if name not in known_tools:
        raise ToolACEFormatError("unknown_tool", name)

    argument_source = source[open_index + 1 : -1].strip()
    arguments: dict[str, JsonValue] = {}
    for raw_argument in _split_top_level(argument_source, ","):
        key, raw_value = _split_argument(raw_argument)
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", key):
            raise ToolACEFormatError("malformed_call_target", f"invalid argument {key}")
        if key in arguments:
            raise ToolACEFormatError(
                "malformed_call_target", f"duplicate argument {key}"
            )
        arguments[key] = _parse_literal(raw_value)
    return ToolCall(name=name, arguments=arguments)


def parse_target(raw_target: str, schemas: Sequence[ToolSchema]) -> CanonicalTarget:
    value = raw_target.strip()
    if not value:
        raise ToolACEFormatError("empty_target")
    starts_bracket = value.startswith("[")
    ends_bracket = value.endswith("]")
    if not starts_bracket and not ends_bracket:
        return CanonicalTarget(calls=())
    if not starts_bracket or not ends_bracket:
        raise ToolACEFormatError("malformed_call_target", "unbalanced call list")

    body = value[1:-1].strip()
    if not body:
        raise ToolACEFormatError("malformed_call_target", "empty call list")
    known_tools = {schema.name for schema in schemas}
    calls = tuple(
        _parse_call(item, known_tools) for item in _split_top_level(body, ",")
    )
    return CanonicalTarget(calls=calls)


def _role(message: object) -> str | None:
    if not isinstance(message, Mapping):
        return None
    role = message.get("from")
    return role if isinstance(role, str) else None


def _decision_id(source_revision: str, row_index: int, turn_index: int) -> str:
    return f"{source_revision}:{row_index}:{turn_index}"


def _context(messages: Sequence[object], stop: int) -> tuple[ChatMessage, ...]:
    context: list[ChatMessage] = []
    for index, message in enumerate(messages[:stop]):
        if not isinstance(message, Mapping):
            raise ToolACEFormatError(
                "malformed_context", f"turn {index} is not an object"
            )
        role = message.get("from")
        content = message.get("value")
        if role not in {"user", "assistant", "tool"} or not isinstance(content, str):
            raise ToolACEFormatError("malformed_context", f"invalid turn {index}")
        context.append(ChatMessage(role=cast(str, role), content=content))
    if not context or context[-1].role != "user":
        raise ToolACEFormatError("malformed_context", "decision does not follow user")
    return tuple(context)


def transform_rows(
    rows: Sequence[object], *, source_revision: str
) -> TransformationResult:
    if not source_revision.strip():
        raise ValueError("source_revision must not be blank")

    accepted: list[DecisionPoint] = []
    rejected: list[RejectedDecision] = []
    row_statuses: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    candidate_decisions = 0
    ineligible_assistant_turns = 0

    for row_index, raw_row in enumerate(rows):
        row_accepted = 0
        row_rejected = 0
        if not isinstance(raw_row, Mapping):
            row_statuses["rejected"] += 1
            continue
        raw_messages = raw_row.get("conversations", [])
        if not isinstance(raw_messages, list):
            row_statuses["rejected"] += 1
            continue
        messages = cast(list[object], raw_messages)
        candidates: list[int] = []
        for turn_index, message in enumerate(messages):
            if _role(message) != "assistant":
                continue
            if turn_index > 0 and _role(messages[turn_index - 1]) == "user":
                candidates.append(turn_index)
            else:
                ineligible_assistant_turns += 1
        candidate_decisions += len(candidates)

        system = raw_row.get("system")
        try:
            if not isinstance(system, str):
                raise ToolACEFormatError("malformed_schema_json", "system is not text")
            schemas = parse_tool_schemas(system)
        except ToolACEFormatError as error:
            for turn_index in candidates:
                decision_id = _decision_id(source_revision, row_index, turn_index)
                rejected.append(
                    RejectedDecision(
                        id=decision_id,
                        row_index=row_index,
                        assistant_turn_index=turn_index,
                        reason=error.reason,
                        detail=error.detail,
                    )
                )
                row_rejected += 1
                reason_counts[error.reason] += 1
            row_statuses["rejected"] += 1
            continue

        for turn_index in candidates:
            decision_id = _decision_id(source_revision, row_index, turn_index)
            try:
                message = messages[turn_index]
                if not isinstance(message, Mapping):
                    raise ToolACEFormatError(
                        "malformed_context", "assistant is not object"
                    )
                raw_target = message.get("value")
                if not isinstance(raw_target, str):
                    raise ToolACEFormatError(
                        "malformed_call_target", "target is not text"
                    )
                target = parse_target(raw_target, schemas)
                decision = DecisionPoint(
                    id=decision_id,
                    source_revision=source_revision,
                    row_index=row_index,
                    assistant_turn_index=turn_index,
                    schemas=schemas,
                    context=_context(messages, turn_index),
                    target=target,
                    raw_target=raw_target,
                )
            except ToolACEFormatError as error:
                rejected.append(
                    RejectedDecision(
                        id=decision_id,
                        row_index=row_index,
                        assistant_turn_index=turn_index,
                        reason=error.reason,
                        detail=error.detail,
                    )
                )
                row_rejected += 1
                reason_counts[error.reason] += 1
            else:
                accepted.append(decision)
                row_accepted += 1
                class_counts[decision.decision_class.value] += 1

        if row_accepted and row_rejected:
            row_statuses["partial"] += 1
        elif row_accepted:
            row_statuses["accepted"] += 1
        else:
            row_statuses["rejected"] += 1

    report = TransformationReport(
        rows_total=len(rows),
        candidate_decisions=candidate_decisions,
        accepted_decisions=len(accepted),
        rejected_decisions=len(rejected),
        ineligible_assistant_turns=ineligible_assistant_turns,
        row_status_counts=dict(sorted(row_statuses.items())),
        decision_class_counts=dict(sorted(class_counts.items())),
        rejection_reason_counts=dict(sorted(reason_counts.items())),
    )
    return TransformationResult(
        accepted=tuple(accepted), rejected=tuple(rejected), report=report
    )
