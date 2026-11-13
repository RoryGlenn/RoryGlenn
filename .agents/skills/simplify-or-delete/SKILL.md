---
name: simplify-or-delete
description: Audit a repository, workflow, agent system, or architecture for unnecessary complexity and propose evidence-backed deletion, consolidation, or simplification. Use when asked to reduce checks, agents, documents, dependencies, services, configuration, or maintenance burden; do not delete or disable anything without explicit authorization.
---

# Simplify or delete

Reduce permanent maintenance cost without removing behavior that users or safety boundaries actually need.

## Principle

AI makes additions cheap and ownership expensive. Treat every component as guilty of cost until its current value and evidence justify keeping it.

## Inputs

- Target repository, subsystem, or workflow.
- Intended user outcome and current constraint.
- Known reliability, security, compliance, and compatibility requirements.
- Usage, latency, failure, maintenance, or adoption evidence when available.

## Workflow

### 1. Define the outcome and constraint

State:

- what outcome matters;
- which bottleneck currently limits it;
- which components are on the critical path;
- what evidence would show that a component is unnecessary.

Do not optimize a subsystem merely because it is large.

### 2. Inventory complexity

Identify:

- agents and delegation layers;
- services, databases, queues, and background workers;
- dependencies and frameworks;
- checks, approvals, and verification calls;
- configuration surfaces and feature flags;
- duplicated documents, specifications, and generated indexes;
- connectors, adapters, and fallback paths;
- abandoned features and permanently blocked work.

For each component, record owner, consumers, runtime or cognitive cost, failure surface, and current evidence of use.

### 3. Classify

Use one disposition:

- **Keep** — necessary and proportionate.
- **Simplify** — retain outcome with fewer moving parts.
- **Consolidate** — merge duplicate authorities or implementations.
- **Make lazy** — remove from default or critical path.
- **Deprecate** — announce bounded removal.
- **Delete** — no justified current value.
- **Measure first** — evidence is insufficient.

### 4. Challenge additions

For every proposed replacement, ask:

- Can existing code or policy absorb this?
- Can a function, script, skill, or existing agent replace a new service or agent?
- Can one authoritative document replace several?
- Does the replacement reduce total lifecycle cost, or only move it?

Do not solve complexity by adding a second complexity-management framework.

### 5. Design reversible removal

For each candidate:

- identify dependencies and consumers;
- define tests that preserve required behavior;
- define migration, rollback, and observation period;
- estimate code, configuration, documentation, runtime, and support removed;
- state risks and evidence gaps.

### 6. Separate proposal from mutation

The first pass is read-only. Do not delete, disable, archive, or change production behavior until the user explicitly selects a candidate.

## Output format

| Candidate | Current purpose | Evidence of use | Cost | Disposition | Safe next test |
| --- | --- | --- | --- | --- | --- |

Then provide:

1. Highest-leverage simplification
2. Safe deletion sequence
3. Behavior that must remain
4. Evidence still needed
5. Expected reduction in maintenance or critical-path cost
