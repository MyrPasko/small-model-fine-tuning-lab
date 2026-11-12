from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from fine_tuning_lab.splits import (
    SplitPlan,
    build_split_plan,
    split_class_counts,
    validate_split_plan,
)
from fine_tuning_lab.toolace import (
    JsonValue,
    TransformationResult,
    canonical_json,
    transform_rows,
)

DATASET_ID = "Team-ACE/ToolACE"
DATASET_REVISION = "6bda777c88d21e5a204703c1ee45597a8fa4f734"
DATA_FILENAME = "data.json"
DATA_SIZE_BYTES = 37_154_735
DATA_SHA256 = "ba12c083fca7e8da48c67ad5b895e495447da7c66e39a2e19742c082e6cb537e"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: JsonValue) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Sequence[dict[str, JsonValue]]) -> None:
    with path.open("w", encoding="utf-8") as destination:
        for value in values:
            destination.write(canonical_json(value) + "\n")


def _load_rows(path: Path) -> list[object]:
    decoded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, list):
        raise TypeError("ToolACE data.json must contain a JSON array")
    return cast(list[object], decoded)


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _profile_payload(
    result: TransformationResult,
    *,
    split_payload: dict[str, JsonValue],
    class_counts: dict[str, dict[str, int]],
    leakage_checks: dict[str, JsonValue],
    source_path: Path,
) -> dict[str, JsonValue]:
    report = result.report
    return {
        "dataset": {
            "filename": DATA_FILENAME,
            "id": DATASET_ID,
            "revision": DATASET_REVISION,
            "sha256": DATA_SHA256,
            "size_bytes": DATA_SIZE_BYTES,
            "source_path": str(source_path.resolve()),
        },
        "rates": {
            "accepted_decision_rate": _rate(
                report.accepted_decisions, report.candidate_decisions
            ),
            "rejected_decision_rate": _rate(
                report.rejected_decisions, report.candidate_decisions
            ),
        },
        "leakage_checks": leakage_checks,
        "schema_version": 1,
        "split_class_counts": {
            split: {key: value for key, value in counts.items()}
            for split, counts in class_counts.items()
        },
        "split_manifest_sha256": cast(str, split_payload["manifest_sha256"]),
        "transformation": result.report.to_dict(),
    }


def prepare_pinned_dataset(
    source_path: Path,
) -> tuple[TransformationResult, SplitPlan]:
    if source_path.stat().st_size != DATA_SIZE_BYTES:
        raise ValueError(
            f"ToolACE size mismatch: expected {DATA_SIZE_BYTES}, "
            f"got {source_path.stat().st_size}"
        )
    source_sha256 = sha256_file(source_path)
    if source_sha256 != DATA_SHA256:
        raise ValueError(
            f"ToolACE SHA-256 mismatch: expected {DATA_SHA256}, got {source_sha256}"
        )

    rows = _load_rows(source_path)
    result = transform_rows(rows, source_revision=DATASET_REVISION)
    split_plan = build_split_plan(
        result.accepted,
        seed=42,
        standard_limit=64,
        strict_limit=64,
        near_schema_threshold=0.85,
    )
    leakage_checks = validate_split_plan(split_plan, result.accepted)
    if leakage_checks["hard_leakage_violation_count"] != 0:
        raise ValueError(f"split leakage validation failed: {leakage_checks}")
    return result, split_plan


def prepare_dataset(source_path: Path, output_dir: Path) -> dict[str, JsonValue]:
    result, split_plan = prepare_pinned_dataset(source_path)
    split_payload = split_plan.to_dict()
    class_counts = split_class_counts(split_plan, result.accepted)
    leakage_checks = validate_split_plan(split_plan, result.accepted)

    output_dir.mkdir(parents=True, exist_ok=True)
    decision_payloads = [decision.to_dict() for decision in result.accepted]
    rejected_payloads = [decision.to_dict() for decision in result.rejected]
    _write_jsonl(output_dir / "decisions.jsonl", decision_payloads)
    _write_jsonl(output_dir / "rejected.jsonl", rejected_payloads)
    _write_json(output_dir / "split_manifest.json", split_payload)

    by_id = {decision.id: decision for decision in result.accepted}
    b0_ids = (*split_plan.standard_ids, *split_plan.strict_ids)
    _write_jsonl(
        output_dir / "b0_decisions.jsonl",
        [by_id[decision_id].to_dict() for decision_id in b0_ids],
    )
    profile = _profile_payload(
        result,
        split_payload=split_payload,
        class_counts=class_counts,
        leakage_checks=leakage_checks,
        source_path=source_path,
    )
    _write_json(output_dir / "profile.json", profile)

    artifact_hashes: dict[str, JsonValue] = {
        filename: sha256_file(output_dir / filename)
        for filename in (
            "b0_decisions.jsonl",
            "decisions.jsonl",
            "profile.json",
            "rejected.jsonl",
            "split_manifest.json",
        )
    }
    summary: dict[str, JsonValue] = {
        "artifact_sha256": artifact_hashes,
        "b0_decisions": len(b0_ids),
        "dataset_sha256": DATA_SHA256,
        "output_dir": str(output_dir.resolve()),
        "schema_version": 1,
        "split_manifest_sha256": split_plan.manifest_hash,
    }
    _write_json(output_dir / "summary.json", summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify and deterministically prepare the pinned ToolACE snapshot."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    summary = prepare_dataset(arguments.source, arguments.output_dir)
    print(canonical_json(summary))


if __name__ == "__main__":
    main()
