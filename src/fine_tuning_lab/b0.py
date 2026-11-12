from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import time
from pathlib import Path
from typing import Any, cast

from fine_tuning_lab.evaluation import Prediction, evaluate_predictions
from fine_tuning_lab.prepare_toolace import (
    DATA_SHA256,
    DATASET_ID,
    DATASET_REVISION,
    prepare_pinned_dataset,
    sha256_file,
)
from fine_tuning_lab.splits import SplitPlan
from fine_tuning_lab.toolace import DecisionPoint, JsonValue, canonical_json

MODEL_ID = "Qwen/Qwen3-1.7B-MLX-4bit"
MODEL_REVISION = "21457c6f51ed54a7c16e988c0844db973815c137"
MAX_NEW_TOKENS = 256
WALL_TIME_LIMIT_SECONDS = 30 * 60
NON_THINKING_PREFILL = "<think>\n\n</think>\n\n"
PROMPT_CONTRACT_VERSION = 1


def build_system_prompt(decision: DecisionPoint) -> str:
    schemas: JsonValue = [schema.to_dict() for schema in decision.schemas]
    return (
        "Select the tool or tools needed for the user's current request. "
        "Return only bracket-style calls in the exact form "
        "[tool_name(argument=value)] when a tool is needed. "
        "Preserve multiple calls in execution order. If no available tool applies, "
        "answer with a short explanation and do not invent a call.\n"
        "Available tool schemas (canonical JSON):\n" + canonical_json(schemas)
    )


def build_messages(decision: DecisionPoint) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": build_system_prompt(decision)}]
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in decision.context
    )
    messages.append({"role": "assistant", "content": NON_THINKING_PREFILL})
    return messages


def build_b0_manifest(
    plan: SplitPlan, by_id: dict[str, DecisionPoint]
) -> dict[str, JsonValue]:
    items: list[JsonValue] = []
    for split, ids in (
        ("standard", plan.standard_ids),
        ("strict_schema_disjoint", plan.strict_ids),
    ):
        items.extend(
            {
                "decision_class": by_id[decision_id].decision_class.value,
                "decision_id": decision_id,
                "prompt_fingerprint": by_id[decision_id].prompt_fingerprint,
                "schema_fingerprint": by_id[decision_id].schema_fingerprint,
                "split": split,
            }
            for decision_id in ids
        )
    payload: dict[str, JsonValue] = {
        "dataset": {
            "id": DATASET_ID,
            "revision": DATASET_REVISION,
            "sha256": DATA_SHA256,
            "split_manifest_sha256": plan.manifest_hash,
        },
        "evaluation_items": items,
        "generation": {
            "decoding": "greedy",
            "max_new_tokens": MAX_NEW_TOKENS,
            "non_thinking_prefill": NON_THINKING_PREFILL,
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "wall_time_limit_seconds": WALL_TIME_LIMIT_SECONDS,
        },
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION},
        "schema_version": 1,
    }
    payload["manifest_sha256"] = hashlib.sha256(
        canonical_json(payload).encode()
    ).hexdigest()
    return payload


def _write_json(path: Path, payload: dict[str, JsonValue]) -> None:
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8")


def _split_for_id(plan: SplitPlan) -> dict[str, str]:
    return {
        **{decision_id: "standard" for decision_id in plan.standard_ids},
        **{decision_id: "strict_schema_disjoint" for decision_id in plan.strict_ids},
    }


def _render_prompt(tokenizer: Any, decision: DecisionPoint) -> str:
    prompt: object = tokenizer.apply_chat_template(
        build_messages(decision),
        tokenize=False,
        continue_final_message=True,
        add_generation_prompt=False,
    )
    if not isinstance(prompt, str):
        raise TypeError("chat template did not return text")
    return prompt


def _generate_prediction(
    model: Any,
    tokenizer: Any,
    decision: DecisionPoint,
    *,
    stream_generate: Any,
    sampler: Any,
) -> Prediction:
    prompt = _render_prompt(tokenizer, decision)
    started = time.perf_counter()
    text = ""
    last_response: Any = None
    for response in stream_generate(
        model,
        tokenizer,
        prompt,
        max_tokens=MAX_NEW_TOKENS,
        sampler=sampler,
    ):
        text += cast(str, response.text)
        last_response = response
    if last_response is None:
        raise RuntimeError("generation returned no response")
    return Prediction(
        decision_id=decision.id,
        output=text,
        latency_seconds=time.perf_counter() - started,
        prompt_tokens=cast(int, last_response.prompt_tokens),
        generation_tokens=cast(int, last_response.generation_tokens),
        peak_memory_gb=cast(float, last_response.peak_memory),
        finish_reason=cast(str | None, last_response.finish_reason),
    )


def run_b0(
    source_path: Path, model_path: Path, output_dir: Path
) -> dict[str, JsonValue]:
    if model_path.name != MODEL_REVISION:
        raise ValueError(
            f"model path must be the pinned snapshot directory {MODEL_REVISION}"
        )
    for required_file in ("config.json", "model.safetensors", "tokenizer.json"):
        if not (model_path / required_file).exists():
            raise FileNotFoundError(model_path / required_file)

    result, plan = prepare_pinned_dataset(source_path)
    by_id = {decision.id: decision for decision in result.accepted}
    manifest = build_b0_manifest(plan, by_id)
    split_by_id = _split_for_id(plan)
    planned_ids = (*plan.standard_ids, *plan.strict_ids)

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "b0_manifest.json"
    result_path = output_dir / "b0_results.jsonl"
    _write_json(manifest_path, manifest)

    started = time.perf_counter()
    mlx_lm = importlib.import_module("mlx_lm")
    sample_utils = importlib.import_module("mlx_lm.sample_utils")
    model, tokenizer = mlx_lm.load(str(model_path))
    sampler = sample_utils.make_sampler(temp=0.0)

    predictions: list[Prediction] = []
    errors = 0
    not_run = 0
    with result_path.open("w", encoding="utf-8") as destination:
        for index, decision_id in enumerate(planned_ids):
            if time.perf_counter() - started >= WALL_TIME_LIMIT_SECONDS:
                for remaining_id in planned_ids[index:]:
                    record: dict[str, JsonValue] = {
                        "decision_id": remaining_id,
                        "split": split_by_id[remaining_id],
                        "status": "not_run_wall_time",
                    }
                    destination.write(canonical_json(record) + "\n")
                    not_run += 1
                break
            decision = by_id[decision_id]
            try:
                prediction = _generate_prediction(
                    model,
                    tokenizer,
                    decision,
                    stream_generate=mlx_lm.stream_generate,
                    sampler=sampler,
                )
            except Exception as error:  # noqa: BLE001 - every item needs a status
                record = {
                    "decision_id": decision_id,
                    "error": f"{type(error).__name__}: {error}",
                    "split": split_by_id[decision_id],
                    "status": "error",
                }
                errors += 1
            else:
                predictions.append(prediction)
                record = {
                    "prediction": prediction.to_dict(),
                    "split": split_by_id[decision_id],
                    "status": "completed",
                }
            destination.write(canonical_json(record) + "\n")
            destination.flush()

    elapsed = time.perf_counter() - started
    decision_map = {decision_id: by_id[decision_id] for decision_id in planned_ids}
    standard_predictions = tuple(
        item for item in predictions if split_by_id[item.decision_id] == "standard"
    )
    strict_predictions = tuple(
        item
        for item in predictions
        if split_by_id[item.decision_id] == "strict_schema_disjoint"
    )
    evaluations: dict[str, JsonValue] = {
        "overall": evaluate_predictions(decision_map, tuple(predictions)).to_dict(),
        "standard": evaluate_predictions(decision_map, standard_predictions).to_dict(),
        "strict_schema_disjoint": evaluate_predictions(
            decision_map, strict_predictions
        ).to_dict(),
    }
    status = "complete" if len(predictions) + errors == len(planned_ids) else "stopped"
    report: dict[str, JsonValue] = {
        "artifacts": {
            "manifest_sha256": sha256_file(manifest_path),
            "results_sha256": sha256_file(result_path),
        },
        "counts": {
            "completed": len(predictions),
            "errors": errors,
            "not_run": not_run,
            "planned": len(planned_ids),
        },
        "environment": {
            "mlx_lm_version": importlib.metadata.version("mlx-lm"),
            "mlx_version": importlib.metadata.version("mlx"),
        },
        "evaluations": evaluations,
        "model_path": str(model_path.resolve()),
        "schema_version": 1,
        "status": status,
        "wall_time_seconds": elapsed,
    }
    report_path = output_dir / "b0_report.json"
    _write_json(report_path, report)
    report["artifacts"] = {
        **cast(dict[str, JsonValue], report["artifacts"]),
        "report_sha256": sha256_file(report_path),
    }
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the bounded EXP-001 B0 baseline on the pinned local model."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("model_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    return parser


def main() -> None:
    arguments = _parser().parse_args()
    report = run_b0(arguments.source, arguments.model_path, arguments.output_dir)
    print(canonical_json(report))


if __name__ == "__main__":
    main()
