# Tasks

## 1. Supported bootstrap

- [x] 1.1 Replace duplicated command logic with the existing GraphQL adapter and
  verify new-project and seed-refresh regressions, including exact field IDs and
  single-select option IDs.
- [x] 1.2 Preserve reconciliation behavior and verify existing seed metadata is
  retained without `--refresh-seed`.
- [x] 1.3 Preserve an existing project's closed state and verify the default
  reconciliation regression passes with `closed` omitted from its update.

## 2. Read-only audit

- [x] 2.1 Add query-only project resolution and verify audit performs queries for
  existing, absent, and duplicate project names.
- [x] 2.2 Clarify audit results and prerequisites in the runbook, then verify the
  documented invocation with a fake GitHub CLI executable.
- [x] 2.3 Verify WIP success and failure, including paginated project items.

## 3. Delivery evidence

- [x] 3.1 Run regression tests, Python compilation, Markdown lint, OpenSpec
  validation, and `git diff --check`, then record exact results.
- [x] 3.2 Inspect the complete diff and hand it to the parent for independent
  review, verification, and publication.

## Workflow follow-up

- Keep independent review, verification, and publication results with the PR.
