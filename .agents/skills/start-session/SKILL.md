---
name: start-session
description: Start or resume a guided-learning session for the Small Model Fine-Tuning Lab. Use only in this repository when the user says "start session", "почни сесію", "розпочни сесію", "продовжимо", or explicitly invokes $start-session. Restore Obsidian context, reconcile it with Git, open one active session record, and give the next bounded student assignment. Do not use for session closure, unrelated repositories, or ordinary theory questions.
---

# Start Small Model Fine-Tuning Session

## Scope

This skill starts a guided-learning session for the repository `small-model-fine-tuning-lab` and its Obsidian project records.

Before writing anything, resolve the Git root and confirm that it is this repository. If the checkout is unrelated, do not mutate repository files or project notes.

Canonical paths on this machine:

- Repository: `/Users/myroslavpasko/projects/small-model-fine-tuning-lab`
- Project notes: `/Users/myroslavpasko/obsidian/Docs/CLAUDE_KASSANDRA/Projects/Small-Model-Fine-Tuning-Lab`
- Current state: `Learning_State.md`
- Session history: `Session_Logs/`
- Project index: `Index.md`
- Roadmap: `Roadmap.md`

Treat absolute paths as machine-specific. If the active checkout moved, use the verified Git root and record the new path in `Learning_State.md`.

## Role and Authority

- Aira teaches, scopes, reviews, verifies evidence, and maintains learning records.
- Myroslav implements code by default.
- Aira may implement code only after an explicit bounded takeover request.
- For a student task, give the behavioral contract, exclusions, acceptance criteria, and evidence to return. Do not provide a code recipe unless requested.
- Repository evidence overrides stale documentation, but discrepancies must be reported rather than silently erased.
- Starting a session authorizes only the context and learning-record updates described here. It does not authorize code changes, commits, pushes, pull requests, dependency installation, downloads, model execution, training, or chat archival.
- Preserve unrelated user changes exactly as found.

## Start Workflow

### 1. Restore the canonical context

1. Determine the current date in `Europe/Kyiv`.
2. Read `Learning_State.md` completely.
3. List `Session_Logs/*.md` and read the lexically latest log completely.
4. Read `Index.md`, `Roadmap.md`, and only the project documents needed for the current phase and next action.
5. Do not create a second plan if `Learning_State.md` already defines a valid next exact action.

### 2. Verify the repository

Inspect:

- Git root, current branch, upstream, HEAD, and recent history;
- working-tree status and relevant diff summary;
- files, tests, and artifacts explicitly claimed by the notes.

Do not run downloads, dependency installation, model loading, training, long benchmarks, or external mutations during session startup. If evidence cannot be checked safely, label it unverified.

### 3. Reconcile state

- Compare the notes with repository evidence.
- Preserve historical claims in the session log; correct only current-state fields in `Learning_State.md`.
- Surface documentation drift, uncommitted work, blockers, and incomplete acceptance criteria.
- If the next action is no longer valid, choose the smallest action that restores the documented route and explain why.

### 4. Resolve one active session record

- If the latest session log is `in-progress` and describes the same unfinished lesson, reuse it and add a short resume entry. Do not create a duplicate.
- Otherwise create `Session_Logs/YYYY-MM-DD_NN.md`, using the next two-digit sequence for the current Kyiv date.
- A new log must include frontmatter plus: goal, entry state, current lesson, boundaries, evidence, blockers, and one next action.
- Set the active log status to `in-progress`.
- Update `Learning_State.md` with the verified Git state, current lesson status, the active session link, and exactly one next action.
- Do not update the global daily log, tracker, or progress memory merely because a session started. Those are synchronized at a meaningful checkpoint or end session unless their active-project pointer is materially wrong.

### 5. Begin the lesson

Return a compact Ukrainian startup brief containing:

- where the project stands;
- what was verified in Git;
- any discrepancy or blocker;
- the purpose of the current checkpoint;
- one bounded student assignment;
- explicit non-goals;
- acceptance criteria and the evidence Myroslav should return.

End with a clear handoff to the student. Do not perform the assignment on Myroslav's behalf.

## Session Boundaries

- `$start-session` owns startup and resume behavior.
- `$end-session` owns session closure and final learning-record reconciliation.
- Do not close or mark a lesson complete during startup.
- Do not create more than one active session log for the same unfinished lesson.
- Do not archive or delete the Codex chat.

## State Ownership

- `Learning_State.md` owns current truth.
- `Session_Logs/` owns chronological evidence.
- Static project documents own experiment design.
- Git owns implementation truth.
