# Design

## Context

The original entry point contained 679 lines of duplicated model and GitHub CLI
logic. `rory_operating_system_data.py` already held the model, while
`rory_operating_system_github.py` resolved item, field, and option IDs for GraphQL
updates. The command had imported neither module.

The installed GitHub CLI is 2.45.0. Its `project item-edit` accepts IDs and lacks
the name-based shortcut used by the current entry point. The existing GraphQL
adapter supports this installed CLI through `gh api graphql --input -`.

## Decisions

- Keep the CLI as argument parsing and orchestration over the existing modules.
  This gives the documented command one implementation for model data and
  GitHub operations. Maintaining a second seed implementation would keep the
  current drift possible.
- Add a query-only project resolver shared with reconciliation. Audit branches
  before any reconciliation call and counts the existing project's items.
  Missing or duplicate project names produce the adapter's normal error.
- Preserve default seed behavior. A new project is seeded, an existing project
  keeps its populated item metadata, and `--refresh-seed` reapplies it explicitly.
- Preserve the existing project's closed state during reconciliation by omitting
  `closed` from the metadata update. Independent review identified the adapter's
  unconditional `closed: false` as a change from the published CLI behavior.
- Intercept the GitHub CLI subprocess boundary in tests while exercising the real
  command, JSON envelope, adapter, item pagination, and field-ID resolution.

## Validation

Mocked runs cover new and existing projects, explicit refresh, text/date/select
values, reused item IDs, audit with zero through four active items, missing and
duplicate projects, and WIP counts across pages. A fake CLI executable also
checks the documented script invocation and its error exit status.

Live GitHub Project behavior remains unverified because the accepted validation
scope uses local fixtures. Independent review and verification are coordinated
by the parent task after the writer's first complete diff.

## Main reconciliation

The reviewed fix was published as `654073a`. Current main is `f78e909`, including
the newer standalone bootstrap, its CI self-check, and unrelated profile and
engineering-workflow changes. The two add/add conflicts are the bootstrap and
its runbook.

Keep the modular GraphQL implementation and port the current main command
contract into it. Retain `--self-check` and `validate_graphql_documents` before
GitHub CLI initialization, `--title`, `--no-seed`, normalized single-select
matching, and the WIP summary with active item titles and the project URL.

Default reconciliation follows current main by adding missing seed issues and
filling empty configured fields while preserving populated values. Explicit
refresh reapplies configured values. Query text/date field values so the
preservation decision uses the stored state. Adopt current main's project README
and seed wording in the shared model.

Merge current main with `--no-commit`, resolve the two conflicts, and keep the
merge pending for the parent to review and commit. Validate the merged bootstrap
and the incoming engineering-system checks through local fixtures. Extend the
bootstrap CI paths, compilation, and regression step to cover the modules and
tests used by the resolved entry point.

## Initial writer validation

- `python3 -B -m unittest discover -s tests -v` passed all ten tests. The suite
  exercises the real command and GraphQL adapter with synthetic subprocess
  responses. Three additional script invocations use a temporary fake `gh`
  executable to check audit success and error exits.
- The same regression suite against a disposable copy of published commit
  `3c5f42ce1ce67e1bb4aaeeaf48d4535d7e5b6444` failed in 14 cases, including
  subtests. A separate baseline fixture reproduced metadata editing during an
  existing-project audit and project creation during a missing-project audit.
- The closed-project reconciliation regression failed with the adapter's
  unconditional `closed: false` update and passed after that input was omitted.
- Python compilation passed for all four source and test files. The documented
  command's `--help` invocation exited successfully.
- A comparison with the published entry point confirmed that the shared model
  preserves every constant, field, seed, and view.
- `npx --yes markdownlint-cli2@0.23.0 README.md docs/rory-operating-system.md
  'openspec/**/*.md'` passed for seven Markdown files.
- `openspec validate repair-operating-system-bootstrap --strict` and
  `git diff --check` passed.

## Merge validation

- The pending merge combines reviewed branch commit `654073a` with main commit
  `f78e909`. Both add/add conflicts are resolved. Fifteen incoming files match
  main byte-for-byte. The bootstrap CI receives the module paths and test step.
- `python3 -B -m unittest discover -s tests -v` passed all 19 tests, including
  offline self-check, malformed documents before GitHub initialization, custom
  title creation and audit, seed skipping, missing-field population, populated
  text/date preservation, normalized options, active titles, read-only audits,
  exact item-field IDs, and closed-state preservation.
- The direct `--self-check` command validated 11 static documents. A subprocess
  test also passed with GitHub CLI absent from `PATH`.
- `python -m py_compile` passed for all seven Python files using an isolated
  bytecode directory. The bootstrap `--help` command passed.
- The shared model and command defaults exactly match the inspected main
  implementation, including its project README and seed wording.
- `python3 -B tools/validate_codex_engineering_system.py` passed its temporary
  installer and worktree lifecycle checks.
- Markdown lint passed all eight README, runbook, and OpenSpec files. Strict
  OpenSpec validation, workflow validation with checksum-verified actionlint
  1.7.12, and `git diff HEAD --check` passed.
- Independent re-review and verification are pending with the parent before the
  merge is committed and published. Live GitHub Project behavior remains
  unverified under the fixture-only validation scope.
