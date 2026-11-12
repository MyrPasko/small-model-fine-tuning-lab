from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from fine_tuning_lab.toolace import (
    DecisionClass,
    DecisionPoint,
    JsonValue,
    canonical_json,
)


def schema_similarity(first: DecisionPoint, second: DecisionPoint) -> float:
    if first.schema_fingerprint == second.schema_fingerprint:
        return 1.0
    return _token_similarity(first.schema_tokens, second.schema_tokens)


def _token_similarity(first: frozenset[str], second: frozenset[str]) -> float:
    union = first | second
    if not union:
        return 1.0
    return len(first & second) / len(union)


def _rank(seed: int, namespace: str, value: str) -> str:
    source = f"{seed}:{namespace}:{value}".encode()
    return hashlib.sha256(source).hexdigest()


def _group_by_row(
    decisions: Sequence[DecisionPoint],
) -> dict[int, tuple[DecisionPoint, ...]]:
    groups: dict[int, list[DecisionPoint]] = defaultdict(list)
    for decision in decisions:
        groups[decision.row_index].append(decision)
    return {
        row_index: tuple(sorted(group, key=lambda item: item.assistant_turn_index))
        for row_index, group in groups.items()
    }


def _select_rows(
    groups: dict[int, tuple[DecisionPoint, ...]],
    *,
    limit: int,
    seed: int,
    namespace: str,
    blocked_rows: set[int],
    blocked_prompts: set[str],
) -> tuple[set[int], tuple[str, ...]]:
    if limit <= 0:
        return set(), ()
    candidates = [
        (row_index, group)
        for row_index, group in groups.items()
        if row_index not in blocked_rows
        and not ({item.prompt_fingerprint for item in group} & blocked_prompts)
    ]
    candidates.sort(key=lambda item: _rank(seed, namespace, str(item[0])))

    selected_rows: set[int] = set()
    selected: list[DecisionPoint] = []
    selected_prompts: set[str] = set()
    class_order = (
        DecisionClass.NO_CALL,
        DecisionClass.SINGLE_CALL,
        DecisionClass.MULTI_CALL,
    )

    while len(selected) < limit:
        progressed = False
        for desired_class in class_order:
            for row_index, group in candidates:
                if row_index in selected_rows:
                    continue
                if not any(item.decision_class == desired_class for item in group):
                    continue
                group_prompts = {item.prompt_fingerprint for item in group}
                if group_prompts & (blocked_prompts | selected_prompts):
                    continue
                if len(selected) + len(group) > limit:
                    continue
                selected_rows.add(row_index)
                selected.extend(group)
                selected_prompts.update(group_prompts)
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break

    selected.sort(key=lambda item: _rank(seed, namespace, item.id))
    return selected_rows, tuple(item.id for item in selected)


@dataclass(frozen=True)
class SplitPlan:
    seed: int
    near_schema_threshold: float
    train_ids: tuple[str, ...]
    standard_ids: tuple[str, ...]
    strict_ids: tuple[str, ...]
    excluded_ids_by_reason: dict[str, tuple[str, ...]]

    def _payload(self) -> dict[str, JsonValue]:
        return {
            "config": {
                "near_schema_threshold": self.near_schema_threshold,
                "seed": self.seed,
            },
            "excluded": {
                reason: list(ids)
                for reason, ids in sorted(self.excluded_ids_by_reason.items())
            },
            "schema_version": 1,
            "splits": {
                "standard": list(self.standard_ids),
                "strict_schema_disjoint": list(self.strict_ids),
                "train": list(self.train_ids),
            },
        }

    @property
    def manifest_hash(self) -> str:
        return hashlib.sha256(canonical_json(self._payload()).encode()).hexdigest()

    def to_dict(self) -> dict[str, JsonValue]:
        payload = self._payload()
        payload["manifest_sha256"] = self.manifest_hash
        return payload


def _sorted_ids(
    decisions: Iterable[DecisionPoint], *, seed: int, namespace: str
) -> tuple[str, ...]:
    return tuple(
        decision.id
        for decision in sorted(
            decisions, key=lambda item: _rank(seed, namespace, item.id)
        )
    )


def build_split_plan(
    decisions: Sequence[DecisionPoint],
    *,
    seed: int,
    standard_limit: int = 64,
    strict_limit: int = 64,
    near_schema_threshold: float = 0.85,
) -> SplitPlan:
    if seed < 0:
        raise ValueError("seed must not be negative")
    if standard_limit < 0 or strict_limit < 0:
        raise ValueError("split limits must not be negative")
    if not 0.0 <= near_schema_threshold <= 1.0:
        raise ValueError("near_schema_threshold must be between zero and one")
    if len({decision.id for decision in decisions}) != len(decisions):
        raise ValueError("decision IDs must be unique")

    groups = _group_by_row(decisions)
    strict_rows, strict_ids = _select_rows(
        groups,
        limit=strict_limit,
        seed=seed,
        namespace="strict",
        blocked_rows=set(),
        blocked_prompts=set(),
    )
    strict_decisions = [
        decision for row_index in strict_rows for decision in groups[row_index]
    ]
    strict_schemas = {
        decision.schema_fingerprint: decision.schema_tokens
        for decision in strict_decisions
    }
    strict_prompts = {item.prompt_fingerprint for item in strict_decisions}

    standard_rows, standard_ids = _select_rows(
        groups,
        limit=standard_limit,
        seed=seed,
        namespace="standard",
        blocked_rows=strict_rows,
        blocked_prompts=strict_prompts,
    )
    test_rows = strict_rows | standard_rows
    test_prompts = {
        decision.prompt_fingerprint
        for row_index in test_rows
        for decision in groups[row_index]
    }

    train: list[DecisionPoint] = []
    excluded: dict[str, list[str]] = defaultdict(list)
    for row_index, group in groups.items():
        if row_index in test_rows:
            continue
        if any(item.prompt_fingerprint in test_prompts for item in group):
            excluded["exact_prompt_overlap"].extend(item.id for item in group)
            continue
        candidate_fingerprint = group[0].schema_fingerprint
        candidate_tokens = group[0].schema_tokens
        if any(
            candidate_fingerprint == strict_fingerprint
            or _token_similarity(candidate_tokens, strict_tokens)
            >= near_schema_threshold
            for strict_fingerprint, strict_tokens in strict_schemas.items()
        ):
            excluded["strict_schema_near_overlap"].extend(item.id for item in group)
            continue
        train.extend(group)

    train_ids = _sorted_ids(train, seed=seed, namespace="train")
    excluded_ids = {
        reason: tuple(sorted(ids)) for reason, ids in sorted(excluded.items())
    }
    return SplitPlan(
        seed=seed,
        near_schema_threshold=near_schema_threshold,
        train_ids=train_ids,
        standard_ids=standard_ids,
        strict_ids=strict_ids,
        excluded_ids_by_reason=excluded_ids,
    )


def split_class_counts(
    plan: SplitPlan, decisions: Sequence[DecisionPoint]
) -> dict[str, dict[str, int]]:
    by_id = {decision.id: decision for decision in decisions}
    result: dict[str, dict[str, int]] = {}
    for name, ids in {
        "train": plan.train_ids,
        "standard": plan.standard_ids,
        "strict_schema_disjoint": plan.strict_ids,
    }.items():
        counts = Counter(by_id[decision_id].decision_class.value for decision_id in ids)
        result[name] = dict(sorted(counts.items()))
    return result


def validate_split_plan(
    plan: SplitPlan, decisions: Sequence[DecisionPoint]
) -> dict[str, JsonValue]:
    by_id = {decision.id: decision for decision in decisions}
    split_ids = {
        "train": plan.train_ids,
        "standard": plan.standard_ids,
        "strict": plan.strict_ids,
    }
    missing_ids = sum(
        decision_id not in by_id for ids in split_ids.values() for decision_id in ids
    )
    rows = {
        name: {
            by_id[decision_id].row_index for decision_id in ids if decision_id in by_id
        }
        for name, ids in split_ids.items()
    }
    row_overlap = (
        len(rows["train"] & rows["standard"])
        + len(rows["train"] & rows["strict"])
        + len(rows["standard"] & rows["strict"])
    )
    train = [by_id[item] for item in plan.train_ids if item in by_id]
    standard = [by_id[item] for item in plan.standard_ids if item in by_id]
    strict = [by_id[item] for item in plan.strict_ids if item in by_id]
    train_prompts = {item.prompt_fingerprint for item in train}
    test_prompts = {item.prompt_fingerprint for item in (*standard, *strict)}
    prompt_overlap = len(train_prompts & test_prompts)

    train_schemas = {item.schema_fingerprint: item.schema_tokens for item in train}
    strict_schemas = {item.schema_fingerprint: item.schema_tokens for item in strict}
    exact_schema_overlap = len(set(train_schemas) & set(strict_schemas))
    near_schema_violations = 0
    maximum_similarity = 0.0
    for strict_fingerprint, strict_tokens in strict_schemas.items():
        for train_fingerprint, train_tokens in train_schemas.items():
            similarity = (
                1.0
                if strict_fingerprint == train_fingerprint
                else _token_similarity(strict_tokens, train_tokens)
            )
            maximum_similarity = max(maximum_similarity, similarity)
            near_schema_violations += int(similarity >= plan.near_schema_threshold)

    hard_violations = (
        missing_ids
        + row_overlap
        + prompt_overlap
        + exact_schema_overlap
        + near_schema_violations
    )
    return {
        "exact_prompt_overlap_count": prompt_overlap,
        "exact_strict_schema_overlap_count": exact_schema_overlap,
        "hard_leakage_violation_count": hard_violations,
        "maximum_strict_to_train_schema_similarity": maximum_similarity,
        "missing_decision_id_count": missing_ids,
        "near_strict_schema_violation_count": near_schema_violations,
        "row_overlap_count": row_overlap,
    }
