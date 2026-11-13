# Proposal

## Why

PR #3 added a GraphQL adapter, but the documented bootstrap command still runs
the older duplicated implementation. Seed updates fail with the installed GitHub
CLI, and `--audit-only` reconciles project metadata before checking WIP.

## What Changes

- Connect the documented command to the existing project model and GraphQL adapter.
- Resolve an existing project through queries when auditing, including an explicit
  error when the project is absent or ambiguous.
- Cover bootstrap, reconciliation, seed refresh, and audit through mocked GitHub
  CLI calls, and clarify the audit command in the runbook.
- Reconcile current main through a merge, retaining its offline self-check,
  custom project title, seed-skipping option, missing-field population,
  normalized option matching, and active-item output.

## Capabilities

### New Capabilities

- `operating-system-project` records the bootstrap and audit behavior already
  promised by the runbook.

### Modified Capabilities

The repository has no existing OpenSpec capabilities.

## Impact

Changes affect the Python command entry point, its GitHub adapter, focused
standard-library regression tests, and `docs/rory-operating-system.md`.
