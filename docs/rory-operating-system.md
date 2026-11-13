# Rory Operating System

`tools/bootstrap_rory_operating_system.py` creates and maintains a private,
personal GitHub Project named **Rory Operating System**.

The project limits active work to three outcomes and makes validation evidence
visible across repositories. Rerunning the bootstrap reuses the project,
fields, views, and seeded issues.

## What it creates

### Fields

- `Outcome`
- `Project`
- `Stage`
- `Evidence level`
- `Next validation`
- `User impact`
- `WIP owner`
- `Review date`
- `External dependency`

### Views

- **Now** — items whose Status is `In Progress`
- **Validation required** — validation-stage work without real-user evidence
- **Externally blocked** — open work with an external dependency
- **Maintenance** — active maintenance work
- **Kill candidates** — active work explicitly marked for removal or shutdown

### Initial work-in-progress set

The script seeds these MasterAgent issues.

- `#171`, `#164`, and `#170` as the three active outcomes
- `#172`, `#94`, `#112`, and `#106` as queued validation or dependency work

Rerunning adds missing seed issues and fills empty configured fields. Populated
values are preserved. Pass `--refresh-seed` to restore their configured project
metadata intentionally.

## Run it

### macOS or Ubuntu

Run from the repository root with Python 3 and an installed, authenticated GitHub
CLI. Bootstrap requires the `project` OAuth scope and uses GraphQL through the
official `gh api` command with resolved project, item, field, and option IDs.

```bash
gh auth status
gh auth refresh -s project
python3 tools/bootstrap_rory_operating_system.py
```

The authenticated GitHub account must be `RoryGlenn` unless `--owner` is
supplied explicitly. Reconciliation sets the project to private and preserves
whether it is open or closed.

## Check the script offline

Validate the delimiters in all static GraphQL documents before account access.

```bash
python3 tools/bootstrap_rory_operating_system.py --self-check
```

A successful check prints `[ok] validated <count> GraphQL documents`.

## Verify the WIP limit

This read-only command requires an existing project and accepts the
`read:project` OAuth scope.

```bash
python3 tools/bootstrap_rory_operating_system.py --audit-only
```

A successful audit prints `[ok] WIP limit: <count>/3`, the active item titles,
and the project URL. It exits with status 2 if the project is missing, the
project name is ambiguous, or more than three items are In Progress. Create a
missing project with the default bootstrap command above.

## Useful options

```text
--refresh-seed  Replace metadata on the seven seeded issues.
--no-seed       Reconcile the project structure without seed updates.
--audit-only    Read the existing project and enforce the three-item WIP limit.
--self-check    Validate static GraphQL without contacting GitHub.
--owner LOGIN   Target another personal GitHub account.
--title TITLE   Use another exact project title.
```

## Operating rule

An item cannot enter **Now** unless another item leaves first. The bootstrap
checks the rule after every normal run and exits nonzero when the project has
more than three active outcomes.
