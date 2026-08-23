"""Declarative model for the Rory Operating System GitHub Project."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Final

TITLE: Final = "Rory Operating System"
OWNER: Final = "RoryGlenn"
MAX_WIP: Final = 3
DESCRIPTION: Final = (
    "Cross-repository operating system for limiting work in progress, "
    "forcing validation, and measuring real user impact."
)
README: Final = textwrap.dedent(
    """
    # Rory Operating System

    This project controls AI-amplified work across repositories. It optimizes
    for verified outcomes, not the volume of code, issues, documents, or agents.

    ## Rules

    1. **Now contains at most three outcomes.** A fourth item cannot enter
       `In Progress` until another item leaves.
    2. Every item states its **Outcome** and next falsifiable
       **Next validation**.
    3. Evidence advances through `Idea -> Mocked -> Integrated -> Real
       environment -> Real user`.
    4. Technically finished is not done while the user outcome is unverified.
    5. Review externally blocked work and kill candidates every week.
    6. Prefer one complete workflow over a larger capability count.

    ## Stages

    - **Diagnose** — identify the outcome, constraint, and smallest test.
    - **Build** — implement only what the test requires.
    - **Validate** — test in the environment or with the user that matters.
    - **Ship** — deliver the validated capability.
    - **Measure** — observe adoption, reliability, time saved, and impact.
    - **Maintain** — keep a proven capability healthy.
    - **Kill** — remove, archive, or stop investing.
    """
).strip()


@dataclass(frozen=True)
class FieldSpec:
    """One desired project field."""

    name: str
    data_type: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class SeedSpec:
    """One issue and its initial operating metadata."""

    number: int
    status: str
    stage: str
    evidence: str
    outcome: str
    validation: str
    review_days: int
    dependency: str = ""

    @property
    def url(self) -> str:
        """Return the canonical MasterAgent issue URL."""

        return f"https://github.com/RoryGlenn/MasterAgent/issues/{self.number}"


@dataclass(frozen=True)
class ViewSpec:
    """One saved project view."""

    name: str
    query: str
    fields: tuple[str, ...]


FIELDS: Final = (
    FieldSpec("Outcome", "TEXT"),
    FieldSpec(
        "Project",
        "SINGLE_SELECT",
        ("MasterAgent", "LineLight", "commitment-issues", "BranchBeacon", "Other"),
    ),
    FieldSpec(
        "Stage",
        "SINGLE_SELECT",
        ("Diagnose", "Build", "Validate", "Ship", "Measure", "Maintain", "Kill"),
    ),
    FieldSpec(
        "Evidence level",
        "SINGLE_SELECT",
        ("Idea", "Mocked", "Integrated", "Real environment", "Real user"),
    ),
    FieldSpec("Next validation", "TEXT"),
    FieldSpec("User impact", "SINGLE_SELECT", ("None", "Expected", "Observed")),
    FieldSpec("WIP owner", "TEXT"),
    FieldSpec("Review date", "DATE"),
    FieldSpec("External dependency", "TEXT"),
)

SEEDS: Final = (
    SeedSpec(
        171,
        "In Progress",
        "Diagnose",
        "Idea",
        "Select one to three Tier-1 employee workflows with exact value, reliability, latency, interaction, and recovery objectives.",
        "Approve bounded workflow specifications that issue #172 can execute unchanged on a managed workstation.",
        7,
    ),
    SeedSpec(
        164,
        "In Progress",
        "Build",
        "Idea",
        "Measure governance, connector initialization, credentials, provider calls, verification, and user interaction separately.",
        "One deterministic benchmark emits stage timings and counts while proving unselected providers remain untouched.",
        14,
    ),
    SeedSpec(
        170,
        "In Progress",
        "Build",
        "Idea",
        "Bind the exact native connector implementation into execution, approval, audit, diagnostics, and performance identity.",
        "Adversarial tests reject implementation drift before connector construction and prove no fallback occurs.",
        14,
    ),
    SeedSpec(
        172,
        "Todo",
        "Validate",
        "Integrated",
        "Prove the Tier-1 workflow is reliable and usable on a representative managed Windows workstation.",
        "Run identical baseline and post-change workloads and issue a ready, ready_with_restrictions, or not_ready recommendation.",
        28,
        "Issues #171, #164, and #170 plus a representative managed Windows 11 environment.",
    ),
    SeedSpec(
        94,
        "Todo",
        "Validate",
        "Integrated",
        "Provide protected credentials and stable non-production fixtures for every provider required by the Tier-1 workflow.",
        "Run exact Tier-1 native-connector cases with independently verified outcomes and cleanup.",
        21,
        "Atlassian, Bitbucket, and Microsoft 365 test identities, permissions, and fixtures.",
    ),
    SeedSpec(
        112,
        "Todo",
        "Build",
        "Idea",
        "Support governed corporate proxy and enterprise-CA connectivity without broadening provider origins or leaking credentials.",
        "A typed provider read succeeds through an authenticated proxy and TLS-inspection path with bounded diagnostics.",
        21,
        "Representative corporate proxy and enterprise CA test environment.",
    ),
    SeedSpec(
        106,
        "Todo",
        "Validate",
        "Idea",
        "Continuously certify the installed MasterAgent artifact as a standard non-administrator user on Windows 11.",
        "Protected Windows certification runs from a clean installed artifact and fails when required native invariants are skipped.",
        28,
        "Protected standard-user Windows 11 runner or VM.",
    ),
)

VIEWS: Final = (
    ViewSpec(
        "Now",
        'status:"In Progress"',
        (
            "Title",
            "Status",
            "Project",
            "Stage",
            "Outcome",
            "Next validation",
            "Evidence level",
            "User impact",
            "WIP owner",
            "Review date",
        ),
    ),
    ViewSpec(
        "Validation required",
        'stage:Validate -evidence-level:"Real user" -status:Done',
        (
            "Title",
            "Status",
            "Project",
            "Stage",
            "Evidence level",
            "Next validation",
            "External dependency",
            "Review date",
        ),
    ),
    ViewSpec(
        "Externally blocked",
        "has:external-dependency -status:Done",
        (
            "Title",
            "Status",
            "Project",
            "External dependency",
            "Next validation",
            "Review date",
        ),
    ),
    ViewSpec(
        "Maintenance",
        "stage:Maintain -status:Done",
        (
            "Title",
            "Status",
            "Project",
            "User impact",
            "Next validation",
            "Review date",
        ),
    ),
    ViewSpec(
        "Kill candidates",
        "stage:Kill -status:Done",
        (
            "Title",
            "Status",
            "Project",
            "Outcome",
            "User impact",
            "Next validation",
            "Review date",
        ),
    ),
)
