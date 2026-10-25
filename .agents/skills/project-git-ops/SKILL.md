---
name: project-git-ops
description: Own Git and GitHub mechanics for the Small Model Fine-Tuning Lab. Use only in this repository whenever work requires inspecting Git state, creating or switching branches, staging changes, committing, pushing, creating or updating pull requests, reviewing checks, merging accepted work, or synchronizing local main. Myroslav does not perform these operations. Do not use for unrelated repositories or as authorization to change implementation scope.
---

# Small Model Fine-Tuning Git Operations

## Ownership

Aira owns all Git and GitHub mechanics for `small-model-fine-tuning-lab`. Myroslav owns learning decisions and implements code by default, but he does not spend time on branch, index, commit, push, pull-request, merge, or main-synchronization operations.

This standing project authorization includes:

- inspecting repository and remote state;
- creating and switching feature branches;
- staging only in-scope changes;
- creating coherent commits;
- pushing branches and configuring upstreams;
- creating and updating pull requests;
- inspecting PR diffs, review state, and checks;
- merging work after its acceptance conditions are met;
- synchronizing local `main` with `origin/main` after merge.

Git ownership is mechanical authority, not permission to implement unrequested product or ML scope.

## Repository Boundary

Before mutating state, confirm the Git root is `/Users/myroslavpasko/projects/small-model-fine-tuning-lab` or the verified relocated checkout of the same GitHub repository. Do not apply this authorization to another repository.

Use `feature/` for new branches unless the project already has an explicitly selected branch name.

## Safe Workflow

1. Inspect branch, upstream, HEAD, status, remotes, and relevant diff before mutation.
2. Preserve unrelated and user-authored changes. Never clean, restore, reset, or overwrite them to simplify Git state.
3. Stage only files that belong to the accepted checkpoint.
4. Run bounded validation appropriate to the change. Record checks not run instead of implying success.
5. Review the exact staged diff before commit. Use a concise conventional commit message that describes the checkpoint.
6. Push the feature branch and verify local/remote ahead-behind state.
7. Create a PR with an accurate summary, validation evidence, and explicit scope boundaries. Attach every created PR to the current task.
8. Review the PR diff and checks. Merge only when required checks pass or no checks are configured, the diff matches the accepted scope, and no unresolved review concern remains.
9. After merge, switch to `main`, fetch or pull with fast-forward-only semantics, and verify local `main` equals `origin/main` with a clean working tree.
10. Update project learning records with the verified branch, commit, PR, merge, and main-sync evidence when the active workflow requires it.

## Guardrails

- Never force-push, hard-reset, rewrite shared history, delete branches, or discard changes without separate explicit authorization.
- Do not merge a PR with failing checks, unresolved conflicts, unexpected files, or unreviewed scope expansion.
- Do not commit secrets, credentials, model weights, datasets, generated checkpoints, or large artifacts.
- Do not claim a PR is merged or `main` is current without verifying GitHub and local Git evidence.
- Do not make Myroslav repeat Git commands merely as a learning exercise; explain relevant Git concepts when they affect project understanding.

## Handoff

Report the resulting branch, commit, PR URL and state, merge commit or squash commit, local `main` synchronization state, checks run, and any blocker. Keep implementation review distinct from Git mechanics.
