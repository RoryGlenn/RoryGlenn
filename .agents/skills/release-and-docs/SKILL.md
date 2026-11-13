---
name: release-and-docs
description: Prepare or review a software release by verifying the exact packaged artifact, installation and upgrade paths, release metadata, documentation, and evidence. Use for release candidates, publishing preparation, changelogs, or documentation completion; do not publish or tag without explicit authorization.
---

# Release and docs

Prove that the exact artifact users receive matches the reviewed source, documented behavior, and release claims.

## Inputs

- Intended version, source commit, and release scope.
- Repository release and documentation rules.
- Package formats and supported platforms.
- Required CI, security, provenance, and publishing gates.

## Workflow

### 1. Freeze the candidate identity

Record:

- full source commit;
- version and tag candidate;
- package name and artifact filenames;
- hashes and sizes;
- toolchain versions;
- required release workflow.

Do not reuse a consumed tag or published version.

### 2. Build the exact artifact

- Build from a clean checkout.
- Inspect the archive or binary contents.
- Confirm required licenses, notices, executable modes, runtime files, and documentation are present.
- Confirm secrets, caches, development state, and unrelated files are absent.

### 3. Test outside the source tree

Use the exact artifact in a clean environment:

- install;
- first-run or initialization;
- representative core workflow;
- upgrade or migration where applicable;
- uninstall or rollback;
- offline or restricted-network behavior when claimed.

Tests against the source checkout do not substitute for artifact tests.

### 4. Review documentation as a contract

Verify:

- README and quickstart commands work;
- documented defaults, limitations, platforms, and security claims match current behavior;
- changelog and release notes describe user-visible changes without exaggeration;
- generated docs and examples are current;
- planned work is not presented as shipped.

Delegate claim review to `adversarial_reviewer` and artifact execution to `verifier` when available.

### 5. Reconcile evidence

Map each release claim to a command, CI result, provider observation, or explicit manual check. Mark unavailable lanes as unverified rather than passed.

### 6. Prepare, but do not publish

Produce the release package, notes, verification record, and exact publishing steps. Do not create tags, releases, registry publications, or announcements without explicit user authorization.

## Output format

1. Candidate identity
2. Artifact inspection
3. Clean-environment verification
4. Documentation changes
5. Required and unavailable gates
6. Release verdict: `ready`, `ready_with_restrictions`, or `not_ready`
7. Exact authorized next action
