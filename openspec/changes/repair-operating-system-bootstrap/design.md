# Design

## Context

The entry point contains 679 lines of duplicated model and GitHub CLI logic.
`rory_operating_system_data.py` already holds the model, while
`rory_operating_system_github.py` already resolves item, field, and option IDs for
GraphQL updates. Neither module is imported by the command.

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
  keeps its item metadata, and `--refresh-seed` reapplies it explicitly.
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

## Writer validation

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
