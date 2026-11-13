---
name: independent-diff-review
description: Review a branch, pull request, commit, or working-tree diff independently from the author, prioritizing correctness, security, behavior regressions, test gaps, and unnecessary complexity. Use when asked to review code or validate a proposed change; do not edit the implementation unless the user separately asks for fixes.
---

# Independent diff review

Review the change from the requirement and observable behavior, not from the author's confidence or narrative.

## Inputs

- Base and head refs, pull request, commit, or exact diff.
- Original issue, acceptance criteria, and relevant specifications.
- Applicable `AGENTS.md` review rules.
- Known environment or test constraints.

When the original requirement is unavailable, state that limitation and infer only from repository evidence.

## Workflow

1. Confirm the exact review range and repository state.
2. Read the requirement before reading the author's summary.
3. Map changed files to the execution paths and public contracts they affect.
4. Delegate to `adversarial_reviewer` for correctness, security, compatibility, and scope analysis.
5. Delegate to `verifier` for targeted behavior checks when commands can run safely.
6. Wait for both results, reconcile duplicates, and independently inspect load-bearing claims.
7. Report only actionable findings. Avoid style-only comments unless style hides a defect, ambiguity, or maintenance risk.

The reviewer and verifier must remain independent of the writer. They must not accept tests merely because they were added; determine whether the tests would detect the claimed regression.

## Finding requirements

Each finding must include:

- severity: blocker, high, medium, or low;
- file and symbol or line reference;
- broken invariant or observable consequence;
- concrete evidence or reproduction path;
- smallest safe correction;
- whether the current tests detect it.

Do not manufacture findings to appear thorough. When no material problem is found, say so and list the reviewed surfaces and unverified risks.

## Required review areas

Check, as applicable:

- requirement coverage and scope drift;
- correctness, state transitions, concurrency, and error handling;
- trust boundaries, secrets, authorization, and untrusted input;
- compatibility, migrations, packaging, and platform behavior;
- test realism, negative paths, and false reassurance;
- public API, CLI, configuration, and documentation changes;
- unnecessary dependencies, abstractions, services, agents, or persistent state;
- rollback, recovery, and partial-failure behavior.

## Output format

### Findings

List findings in descending severity. Put evidence before optional improvements.

### Verification performed

Give exact commands and results, or state why verification could not run.

### Unverified risks

Name the remaining uncertainty precisely.

### Verdict

Use one of:

- `ready`
- `ready_with_corrections`
- `not_ready`
