## Purpose

Coordinate Rory's cross-repository work in a private GitHub Project with bounded
active work and a command that can also audit the existing board read-only.

## ADDED Requirements

### Requirement: Bootstrap writes exact project item fields

The command SHALL seed a new project and explicitly refreshed projects with the
configured text, date, and single-select values using supported GitHub operations
and resolved project, item, field, and option identifiers.

#### Scenario: New project

- **WHEN** the named project is absent and the default command runs
- **THEN** the project is created with its fields and views, and all configured
  issues receive their initial metadata.

#### Scenario: Existing project reconciliation

- **WHEN** the named project exists and the default command runs
- **THEN** project metadata, fields, and views are reconciled while existing seed
  item metadata is retained.

#### Scenario: Existing closed project reconciliation

- **WHEN** the named project is closed and the default command runs
- **THEN** the project stays closed while its metadata, fields, and views are
  reconciled.

#### Scenario: Explicit seed refresh

- **WHEN** the command runs with `--refresh-seed` for an existing project
- **THEN** its configured seed metadata is reapplied using existing item IDs.

### Requirement: Audit reads existing state

The `--audit-only` command SHALL resolve the existing named project and check its
WIP count using read-only operations. It SHALL fail with a clear error when the
project is absent or its name is ambiguous.

#### Scenario: Existing project audit

- **WHEN** the named project exists and an audit runs
- **THEN** the command reports its WIP count with zero project mutations.

#### Scenario: Project is absent

- **WHEN** the named project is absent and an audit runs
- **THEN** the command fails with an error identifying the missing project and
  makes zero project mutations.

#### Scenario: Project name is ambiguous

- **WHEN** multiple projects have the expected name and an audit runs
- **THEN** the command fails with an ambiguity error and makes zero project
  mutations.

### Requirement: WIP audit enforces the three-item limit

The command SHALL count all project items whose Status is In Progress, including
paginated results, and fail when that count exceeds three.

#### Scenario: WIP is within the limit

- **WHEN** the project has at most three items In Progress
- **THEN** the command reports the count and succeeds.

#### Scenario: WIP exceeds the limit across pages

- **WHEN** the project has four items In Progress across multiple item pages
- **THEN** the command reports the violation and fails.
