# Codex engineering system

This system turns Rory's existing AI-assisted engineering habits into a reusable
Codex workflow that applies across repositories.

It standardizes four things:

1. selecting the correct workflow;
2. isolating implementation with worktrees;
3. separating writer, reviewer, and verifier responsibilities;
4. requiring observable evidence before work is called complete.

The source lives in this repository and installs into Codex's user-scoped
locations. Repository-specific `AGENTS.md` files still add or override local
rules.

## Installed components

### Skills

| Skill | Use |
| --- | --- |
| `issue-to-tested-pr` | Move one accepted issue through implementation, review, verification, and PR preparation |
| `independent-diff-review` | Review a PR, branch, commit, or local diff independently from the author |
| `release-and-docs` | Verify the exact package, clean installation, release evidence, and documentation |
| `simplify-or-delete` | Find unnecessary complexity and design safe consolidation or deletion |

The checked-in source is under `.agents/skills/`. The installer makes the
skills available from `~/.agents/skills/`, which Codex scans for user-level
skills.

### Custom agents

| Agent | Access | Responsibility |
| --- | --- | --- |
| `implementation_owner` | Workspace write | The only source-code writer for one accepted change |
| `adversarial_reviewer` | Read only | Correctness, security, regression, test, scope, and complexity review |
| `verifier` | Workspace write | Run tests and clean-environment checks without changing product source |

The source is under `.codex/agents/`. The installer exposes the files from
`~/.codex/agents/`.

### Global guidance

The installer adds one bounded managed block to `~/.codex/AGENTS.md`. It tells
Codex when to use each skill and establishes these rules:

- no more than three active engineering lanes for one outcome;
- one writer per change;
- review and verification begin after the first stable diff;
- repository-local instructions remain authoritative when stricter;
- no unrun check may be reported as passed;
- no merge, publication, release, deletion, send, or permission change occurs
  without explicit authorization.

The installer also sets:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
interrupt_message = true
```

Existing unrelated Codex configuration is preserved.

### Worktree helper

`codex-lanes` provides a safe CLI/IDE fallback when the Codex app's built-in
Worktree mode is not being used.

It creates worktrees below:

```text
~/.codex/worktrees/<repository>-<identity>/<lane>
```

It refuses to create a fourth managed lane and refuses to remove a dirty lane.

## Install

Run from the cloned profile repository.

### macOS or Ubuntu

```bash
cd ~/RoryGlenn
git pull --ff-only

python3 tools/install_codex_engineering_system.py --dry-run
python3 tools/install_codex_engineering_system.py
```

The default uses symbolic links, so `git pull` updates the installed skills and
agents immediately. Codex supports symlinked skill directories.

Restart Codex after the first installation. In an interactive Codex session,
run `/skills` or type `$` to confirm the four workflow skills appear.

The lane helper is installed at `~/.local/bin/codex-lanes`. When that directory
is not already on `PATH`, add this to `~/.zshrc` or the applicable shell file:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Windows

The installer automatically copies files instead of creating symbolic links:

```powershell
python tools\install_codex_engineering_system.py
```

Rerun the installer after pulling updates.

## Normal workflow

### Accepted issue to PR

Start a worktree chat in the Codex app and use:

```text
$issue-to-tested-pr implement issue #164 from the accepted requirements.
Use one writer, then independent review and verification.
```

The expected execution model is:

```text
Parent coordinator
    -> implementation_owner: one writer
    -> stable first diff
    -> adversarial_reviewer: read-only review
    -> verifier: exact tests and behavior evidence
    -> parent reconciles findings and prepares the PR
```

The reviewer receives the original requirement and the diff, not merely the
writer's explanation. The verifier reports exact commands and distinguishes
passed, failed, skipped, unavailable, and flaky checks.

### Independent review

```text
$independent-diff-review review this branch against main.
Use adversarial_reviewer and verifier, wait for both, and return findings in
severity order.
```

This workflow does not edit the implementation unless a separate fix is
requested.

### Release preparation

```text
$release-and-docs prepare the current commit as a release candidate.
Verify the exact built artifact outside the source checkout and reconcile every
documentation claim.
```

The workflow prepares evidence but does not tag or publish without explicit
authorization.

### Complexity reduction

```text
$simplify-or-delete audit this subsystem for controls, agents, documents, and
services that no longer justify their lifecycle cost. Keep the first pass
read-only.
```

## Worktrees

The Codex app's built-in Worktree mode is the preferred path:

1. Start a new chat and select **Worktree**.
2. Choose the base branch.
3. Give the writer one accepted issue.
4. Create a branch in that worktree when the diff is ready.
5. Review and test before handoff or PR creation.

For CLI or IDE work:

```bash
cd /path/to/repository

codex-lanes create issue-164 --role author --base main
codex-lanes create review-164 --role review --base codex/issue-164
codex-lanes audit
codex-lanes list
```

After committing or otherwise preserving all work:

```bash
codex-lanes remove review-164
codex-lanes remove issue-164
```

Removal retains the author branch intentionally. The helper never discards a
dirty worktree.

## Update and audit

```bash
cd ~/RoryGlenn
git pull --ff-only

python3 tools/install_codex_engineering_system.py
python3 tools/install_codex_engineering_system.py --self-check
```

Validate the checked-in system and its full temporary install/worktree
lifecycle:

```bash
python3 tools/validate_codex_engineering_system.py
```

## Uninstall

Preview:

```bash
python3 tools/install_codex_engineering_system.py --uninstall --dry-run
```

Apply:

```bash
python3 tools/install_codex_engineering_system.py --uninstall
```

The uninstaller removes only files that are still owned and unchanged. It
preserves modified copies, unrelated skills, unrelated custom agents, and
non-managed `AGENTS.md` or `config.toml` content.

## Boundaries

- The system coordinates engineering work; it does not replace repository
  requirements, CI, code ownership, or human authorization.
- Skills are instructions, not permissions.
- Reviewer and verifier conclusions remain evidence to be reconciled by the
  parent.
- Parallel agents consume more tokens. Use them where independence or reduced
  context pollution materially improves quality.
- Read-heavy work is safer to parallelize than overlapping code edits.
- The three-thread setting is a ceiling, not a target.
