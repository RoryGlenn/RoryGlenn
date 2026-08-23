# Rory Operating System

`tools/bootstrap_rory_operating_system.py` creates and maintains a private,
personal GitHub Project named **Rory Operating System**.

The project limits active work to three outcomes and makes validation evidence
visible across repositories. The bootstrap is idempotent: rerunning it reuses
the project, fields, views, and seeded issues rather than creating duplicates.

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

The script seeds these MasterAgent issues:

- `#171`, `#164`, and `#170` as the three active outcomes
- `#172`, `#94`, `#112`, and `#106` as queued validation or dependency work

Existing seeded items are left unchanged by default. Pass `--refresh-seed` to
restore their configured project metadata intentionally.

## Run it

### macOS or Ubuntu

Install and authenticate the GitHub CLI, then authorize Projects access once:

```bash
gh auth status
gh auth refresh -s project
python3 tools/bootstrap_rory_operating_system.py
```

The authenticated GitHub account must be `RoryGlenn` unless `--owner` is
supplied explicitly.

## Verify the WIP limit

This read-only command fails when more than three project items are in
`In Progress`:

```bash
python3 tools/bootstrap_rory_operating_system.py --audit-only
```

## Useful options

```text
--refresh-seed  Replace metadata on the seven seeded issues.
--no-seed       Create the project structure without adding seed issues.
--audit-only    Perform no mutation; enforce the three-item WIP limit.
--owner LOGIN   Target another personal GitHub account.
--title TITLE   Use another exact project title.
```

## Operating rule

An item cannot enter **Now** unless another item leaves first. The bootstrap
checks the rule after every normal run and exits nonzero when the project has
more than three active outcomes.
