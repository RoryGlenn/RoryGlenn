# Rory Operating System

`tools/bootstrap_rory_operating_system.py` creates a private, user-level GitHub
Project that coordinates work across repositories. It limits active work,
requires a falsifiable next validation, and separates technical completion from
observed user impact.

## Result

The bootstrap creates or reuses a project named **Rory Operating System**.

### Fields

| Field | Type | Values or purpose |
| --- | --- | --- |
| Outcome | Text | User or organizational result, not implementation output |
| Project | Single select | MasterAgent, LineLight, commitment-issues, BranchBeacon, Other |
| Stage | Single select | Diagnose, Build, Validate, Ship, Measure, Maintain, Kill |
| Evidence level | Single select | Idea, Mocked, Integrated, Real environment, Real user |
| Next validation | Text | Next observation that could prove the work wrong or incomplete |
| User impact | Single select | None, Expected, Observed |
| WIP owner | Text | Person responsible for moving the outcome |
| Review date | Date | Non-binding reassessment date |
| External dependency | Text | Human, permission, environment, account, or provider blocker |

### Views

| View | Filter |
| --- | --- |
| Now | `status:"In Progress"` |
| Validation required | `stage:Validate -evidence-level:"Real user" -status:Done` |
| Externally blocked | `has:external-dependency -status:Done` |
| Maintenance | `stage:Maintain -status:Done` |
| Kill candidates | `stage:Kill -status:Done` |

The script fails when more than three items have `Status = In Progress`.

### Initial work

A newly created project is seeded with the MasterAgent work required to prove one
useful employee workflow rather than continue expanding raw capability count:

- `RoryGlenn/MasterAgent#171` — define Tier-1 workflows
- `RoryGlenn/MasterAgent#164` — instrument performance and governance overhead
- `RoryGlenn/MasterAgent#170` — bind connector implementation identity
- `RoryGlenn/MasterAgent#172` — managed-workstation pilot
- `RoryGlenn/MasterAgent#94` — protected provider fixtures and credentials
- `RoryGlenn/MasterAgent#112` — corporate proxy and enterprise CA support
- `RoryGlenn/MasterAgent#106` — Windows 11 certification

Exactly the first three enter **Now**. The remainder begin in **Todo** and appear
in the appropriate validation or blocked views.

## Run once

The GitHub CLI must be authenticated as `RoryGlenn` with the `project` OAuth
scope. The script uses Python's standard library and the official `gh project`
and `gh api` commands.

### macOS

```bash
brew install gh
gh auth login --hostname github.com --git-protocol https --web
gh auth refresh --hostname github.com --scopes project

git clone https://github.com/RoryGlenn/RoryGlenn.git
cd RoryGlenn
python3 tools/bootstrap_rory_operating_system.py
```

### Ubuntu 24.04

```bash
sudo apt update
sudo apt install -y gh
gh auth login --hostname github.com --git-protocol https --web
gh auth refresh --hostname github.com --scopes project

git clone https://github.com/RoryGlenn/RoryGlenn.git
cd RoryGlenn
python3 tools/bootstrap_rory_operating_system.py
```

The final line printed by the script contains the private project URL.

## Reconcile or audit

Rerunning the default command reconciles project metadata, fields, and views. It
does not reapply the seed metadata when the project already exists.

```bash
python3 tools/bootstrap_rory_operating_system.py
```

Reapply the initial metadata to the seven seeded MasterAgent issues:

```bash
python3 tools/bootstrap_rory_operating_system.py --refresh-seed
```

Check the current three-item WIP limit:

```bash
python3 tools/bootstrap_rory_operating_system.py --audit-only
```

## Safety boundaries

- The project remains private.
- The script does not modify issue bodies, labels, milestones, assignees,
  repository files, branches, or pull requests.
- A project field with the expected name is reused rather than replaced.
- The script performs no repository deletion, issue closure, merge, release, or
  external provider action.
- The WIP assertion fails closed when more than three items are active.
