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
- **THEN** project metadata, fields, and views are reconciled, missing seed
  issues and empty configured fields are populated, and populated seed item
  metadata is retained.

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

### Requirement: Static documents can be checked offline

The command SHALL support `--self-check` to validate the delimiters of all static
GraphQL documents and report the count before GitHub access is initialized.
Normal commands SHALL perform that validation before GitHub operations.

#### Scenario: Offline self-check

- **WHEN** `--self-check` runs with GitHub CLI unavailable
- **THEN** valid static documents produce a successful count with zero GitHub
  operations.

#### Scenario: Truncated document

- **WHEN** a static GraphQL document is truncated and a command runs
- **THEN** the command fails before GitHub access is initialized.

### Requirement: Command options select reconciliation behavior

The command SHALL accept an exact project title through `--title` and omit seed
issue and item-field mutations when `--no-seed` is supplied.

#### Scenario: Custom title

- **WHEN** a command supplies `--title`
- **THEN** project lookup, creation, and metadata reconciliation use that exact
  title.

#### Scenario: Structure-only reconciliation

- **WHEN** the command runs with `--no-seed`
- **THEN** it reconciles project metadata, fields, and views, and audits WIP
  without seed issue or item-field mutations.

### Requirement: Project value matching tolerates formatting

Single-select option and active Status comparisons SHALL ignore case and
repeated whitespace while requiring a unique matching option for updates.

#### Scenario: Formatted option names

- **WHEN** configured options differ only by case or repeated whitespace
- **THEN** seed updates resolve the existing option IDs and the WIP audit counts
  active items correctly.
