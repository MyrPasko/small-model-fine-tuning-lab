---
name: end-session
description: Close a guided-learning session for the Small Model Fine-Tuning Lab. Use only in this repository when the user says "end session", "finish session", "закінчи сесію", or explicitly invokes $end-session. Verify repository evidence, update the active session log and learning state, synchronize relevant learning records, and preserve one exact next action. Do not use for starting a session, ordinary checkpoints, status requests, unrelated repositories, or theory questions.
---

# End Small Model Fine-Tuning Session

## Scope

This skill closes a guided-learning session for the repository `small-model-fine-tuning-lab` and reconciles its Obsidian project records with repository evidence. `$start-session` owns startup and resume behavior.

Before acting, resolve the Git root and confirm that it is this repository. If the current checkout is unrelated, do not mutate its files or the vault records.

Canonical paths on this machine:

- Repository: `/Users/myroslavpasko/projects/small-model-fine-tuning-lab`
- Project notes: `/Users/myroslavpasko/obsidian/Docs/CLAUDE_KASSANDRA/Projects/Small-Model-Fine-Tuning-Lab`
- Current state: `Learning_State.md`
- Session history: `Session_Logs/`
- Project index: `Index.md`
- Decisions: `Decision-Log.md`
- Global learning pointer: `/Users/myroslavpasko/obsidian/Docs/AI/AGENTIC_LEARNING/Progress_Memory.md`
- Global tracker: `/Users/myroslavpasko/obsidian/Docs/AI/AGENTIC_LEARNING/Agentic_Learning_Tracker.md`
- Global daily logs: `/Users/myroslavpasko/obsidian/Docs/AI/AGENTIC_LEARNING/Daily_Logs/`

Treat absolute paths as machine-specific. If the repository moved, locate it from the active checkout and update `Learning_State.md` after verification.

## Role and Authority

- Aira teaches, scopes, reviews, verifies evidence, and maintains learning records.
- Myroslav implements code by default.
- Aira may implement code only after an explicit bounded takeover request.
- Aira owns all Git and GitHub mechanics under `$project-git-ops`; Myroslav is not assigned branch, staging, commit, push, PR, merge, or main-sync commands.
- Repository evidence overrides stale notes.
- A request to end a session authorizes the learning-record updates described here. Standing Git/GitHub authority is defined separately by `$project-git-ops`; ending a session does not authorize code changes, chat archival, model or dataset downloads, dependency installation, backend runs, or training.
- Preserve unrelated user changes. Never clean or revert the working tree merely to make the session state simpler.

## Workflow

When the user says `end session`, `finish session`, `закінчи сесію`, or explicitly invokes `$end-session`, complete this workflow.

### 1. Resolve the active record

- Read `Learning_State.md` and the latest session log.
- Reuse the current `in-progress` log when it represents this session.
- Otherwise create `Session_Logs/YYYY-MM-DD_NN.md`, where `NN` is the next two-digit sequence for the current Kyiv date.
- Never create a second log for the same session.

### 2. Verify repository evidence

- Inspect branch, HEAD, status, diff summary, recent history, and relevant artifacts.
- Run only safe, bounded checks appropriate to the current checkpoint.
- Do not trigger downloads, model loading, training, long benchmarks, or external mutations merely to close a session.
- If a relevant check was not run, record `not run`; never infer a pass.
- Preserve uncommitted and unrelated work exactly as found.

### 3. Close the session log

Record:

- original goal and actual result;
- verified repository evidence;
- files or artifacts changed;
- commands or tests run and their outcomes;
- questions answered;
- mistakes, weak spots, and corrections;
- explicit implementation takeovers by Aira, if any;
- blockers and unresolved scope;
- verdict;
- one exact next action.

Set the session status honestly. A stopped but unfinished session is `partial` or `in-progress`, not `done`.

### 4. Refresh `Learning_State.md`

Keep it compact and current. Update:

- current phase, lesson, and status;
- repository path, GitHub URL, branch, HEAD, and worktree state;
- completed and remaining work;
- active boundaries and blockers;
- **Наступна точна дія**;
- link to the latest session log;
- `updated` date.

Do not turn `Learning_State.md` into a chronological diary. Move historical detail into the session log.

### 5. Synchronize learning control

- Update today's global daily log when a real learning session occurred.
- Update the tracker row with the verified verdict and evidence.
- Update `Progress_Memory.md` when current phase, active repository, blocker, or next action changed.
- Update the general plan only when the route or governing principles changed.
- Update `Decision-Log.md` only for an actual durable decision.
- Keep `Index.md` links valid and point its continuity section at the latest state/log when needed.

### 6. Verify documentation

- Use `apply_patch` for edits.
- Preserve frontmatter, Wikilinks, naming conventions, and unrelated content.
- If the vault is outside writable roots, stage the exact files, request approval for only those targets, synchronize them, and compare staged and saved copies.
- Confirm every intended file exists, frontmatter is valid, new Wikilinks resolve, and no unrelated note changed.

### 7. Return the closeout

Return a compact closeout containing:

- session verdict;
- verified work completed;
- tests or checks run;
- remaining blockers;
- next exact action;
- links to `Learning_State.md` and the closed session log.

Do not archive or delete the Codex chat unless the user separately asks for that action.

## Boundaries

- Use `$start-session` for startup and resume.
- Treat ordinary checkpoint review and status questions as normal in-session work; do not route them to this skill.
- Do not perform implementation work merely because the session is ending.
- Do not create a second session log when the current `in-progress` log already represents this session.

## State Ownership

- `Learning_State.md` owns current truth.
- `Session_Logs/` owns chronological detail and evidence.
- Static project documents own product and experiment design.
- Git owns technical implementation truth.
- Global agentic-learning notes point to the active project; they should not duplicate the entire project state.
