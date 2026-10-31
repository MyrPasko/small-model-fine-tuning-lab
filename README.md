# Small Model Fine-Tuning Lab

A controlled local experiment for measuring whether QLoRA can improve structured tool calling in a small language model.

The first experiment, **EXP-001 — Tiny Tool Router**, asks a model to convert a natural-language request plus a set of tool schemas into the correct structured tool calls. A fluent answer is not sufficient: the calls must be parseable, select the correct tools, contain valid typed arguments, and avoid unnecessary calls.

## Research Question

Can QLoRA fine-tuning make `Qwen/Qwen3-1.7B` more reliable at producing valid, correct, and executable tool calls than the same unfine-tuned model?

## Proposed Stack

- **Model:** `Qwen/Qwen3-1.7B`
- **Training dataset:** `Team-ACE/ToolACE`
- **Method:** QLoRA-style adapter training on quantized base weights
- **Primary backend candidate:** MLX-LM on Apple Silicon
- **Fallback/reference backend:** Transformers with PEFT

The exact model revision, dataset revision, backend version, and quantization configuration remain subject to a compatibility preflight. None is locked merely by appearing in this README.

## Experiment Matrix

| ID | Training | Data | Purpose |
|---|---|---|---|
| B0 | None | Frozen evaluation sets | Measure the native model baseline |
| S1 | Tiny bounded QLoRA smoke run | Small ToolACE training subset | Validate the complete pipeline, adapter save, and fresh-process reload |
| E1 | Approved QLoRA run | Frozen ToolACE training split | Measure the primary fine-tuning result against B0 |

The same model, prompts, parsers, evaluation sets, and scoring rules must be used when comparing B0 with E1.

## Data Boundaries

- The owner does not create, label, clean, or manually repair training examples.
- Raw ToolACE data remains immutable and is transformed automatically into a canonical JSON intermediate representation.
- Every source row must receive an explicit terminal status such as accepted or rejected-with-reason.
- Standard evaluation must be conversation-disjoint and protected against near duplicates.
- A separate schema-disjoint test must contain normalized tool schemas that never appear in training.
- Berkeley Function Calling Leaderboard (BFCL) data is evaluation-only. It must not influence training, prompt tuning, early stopping, hyperparameters, or model selection.

## Evaluation Contract

The experiment prioritizes structural and behavioral evidence:

- parseable-output rate;
- exact tool selection and call-set match;
- required and invented argument errors;
- typed argument-value correctness;
- multiple-call completeness and order;
- no-call precision, recall, and F1;
- deterministic mock-execution pass rate;
- schema-disjoint generalization;
- latency, memory, wall time, and adapter size.

BLEU, ROUGE, and subjective fluency are not primary success metrics for this task.

## Development Checks

Install the exact locked environment:

```shell
uv sync --locked
```

Run the complete local quality gate:

```shell
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

`pyproject.toml` declares the supported ranges and tool configuration. The tracked `uv.lock` records the exact resolved dependency versions used by the project.

## Non-Goals

- training on BFCL;
- manual dataset labeling or repair;
- a hyperparameter sweep in the first experiment;
- production deployment or arbitrary real-world tool execution;
- claiming success from training loss or fluent-looking examples alone;
- automatically proceeding from B0 to S1 or from S1 to E1 without review.

## Evidence Boundary

This README defines the experiment contract; it is not evidence that the pipeline works.

At the current repository-foundation stage:

- no ML dependencies have been installed;
- no model or dataset has been downloaded;
- no backend preflight has passed;
- no baseline, smoke run, or full training run has been executed;
- no model-quality claim has been established.

Each future claim must be backed by reproducible configuration, frozen manifests, checksums, test output, and generated reports committed or referenced by the relevant experiment record.
