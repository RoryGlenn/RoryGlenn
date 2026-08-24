<!-- RORY_CODEX_ENGINEERING_SYSTEM:START -->
## Rory engineering workflow

Optimize for verified user or organizational outcomes, not the volume of code, issues, documents, or agents.

### Workflow selection

- Use `$issue-to-tested-pr` for accepted non-trivial features, bugs, refactors, migrations, and architecture changes.
- Use `$independent-diff-review` for pull request, branch, commit, or working-tree review.
- Use `$release-and-docs` for release candidates, package verification, changelogs, and documentation completion.
- Use `$simplify-or-delete` when complexity, governance, checks, agents, documents, dependencies, or maintenance burden are the problem.

Repository-local `AGENTS.md` instructions remain authoritative when they are stricter or more specific.

### Parallelism and worktrees

- Keep at most three active engineering lanes for one outcome.
- Use exactly one source-code writer per change. Never run overlapping write agents against the same files.
- Prefer a Codex worktree for isolated implementation or another independent write task.
- Keep the local checkout as the integration and decision lane when practical.
- Start independent review and verification only after the writer has produced a stable first diff.
- Parallelize read-heavy exploration, review, tests, and log analysis before parallelizing writes.

### Role separation

- The writer implements and tests.
- The reviewer starts from the requirement and diff, not the writer's justification.
- The verifier runs exact commands and observable behavior checks without editing product source.
- The parent agent reconciles evidence and owns the final recommendation.

### Evidence and completion

- State exact commands and results. Never describe an unrun check as passed.
- Distinguish mocked, integrated, real-environment, and real-user evidence.
- Prefer the smallest complete change and preserve unrelated work.
- Do not add a production dependency, persistent service, new agent, database, or authoritative document without showing why existing mechanisms are insufficient.
- Do not merge, publish, release, send, delete, or change permissions without explicit authorization.
- When blocked by external authority, complete all useful local preparation and identify the smallest user-only action.
<!-- RORY_CODEX_ENGINEERING_SYSTEM:END -->
