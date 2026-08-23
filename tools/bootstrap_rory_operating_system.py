#!/usr/bin/env python3
"""Create Rory's private cross-repository GitHub Projects operating board.

The script creates or reuses a user-level project named ``Rory Operating
System``, installs the operating fields and saved views, seeds the current
MasterAgent priorities, and fails when more than three items are active.

Requirements
------------
- GitHub CLI (``gh``)
- authentication as ``RoryGlenn``
- a token with the ``project`` scope
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final, Mapping, Sequence

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


class BootstrapError(RuntimeError):
    """Raised when the project cannot be reconciled safely."""


@dataclass(frozen=True)
class Field:
    """One desired project field."""

    name: str
    data_type: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class Seed:
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
class View:
    """One saved project view."""

    name: str
    query: str
    fields: tuple[str, ...]


FIELDS: Final = (
    Field("Outcome", "TEXT"),
    Field(
        "Project",
        "SINGLE_SELECT",
        ("MasterAgent", "LineLight", "commitment-issues", "BranchBeacon", "Other"),
    ),
    Field(
        "Stage",
        "SINGLE_SELECT",
        ("Diagnose", "Build", "Validate", "Ship", "Measure", "Maintain", "Kill"),
    ),
    Field(
        "Evidence level",
        "SINGLE_SELECT",
        ("Idea", "Mocked", "Integrated", "Real environment", "Real user"),
    ),
    Field("Next validation", "TEXT"),
    Field("User impact", "SINGLE_SELECT", ("None", "Expected", "Observed")),
    Field("WIP owner", "TEXT"),
    Field("Review date", "DATE"),
    Field("External dependency", "TEXT"),
)

SEEDS: Final = (
    Seed(
        171,
        "In Progress",
        "Diagnose",
        "Idea",
        "Select one to three Tier-1 employee workflows with exact value, reliability, latency, interaction, and recovery objectives.",
        "Approve bounded workflow specifications that issue #172 can execute unchanged on a managed workstation.",
        7,
    ),
    Seed(
        164,
        "In Progress",
        "Build",
        "Idea",
        "Measure governance, connector initialization, credentials, provider calls, verification, and user interaction separately.",
        "One deterministic benchmark emits stage timings and counts while proving unselected providers remain untouched.",
        14,
    ),
    Seed(
        170,
        "In Progress",
        "Build",
        "Idea",
        "Bind the exact native connector implementation into execution, approval, audit, diagnostics, and performance identity.",
        "Adversarial tests reject implementation drift before connector construction and prove no fallback occurs.",
        14,
    ),
    Seed(
        172,
        "Todo",
        "Validate",
        "Integrated",
        "Prove the Tier-1 workflow is reliable and usable on a representative managed Windows workstation.",
        "Run identical baseline and post-change workloads and issue a ready, ready_with_restrictions, or not_ready recommendation.",
        28,
        "Issues #171, #164, and #170 plus a representative managed Windows 11 environment.",
    ),
    Seed(
        94,
        "Todo",
        "Validate",
        "Integrated",
        "Provide protected credentials and stable non-production fixtures for every provider required by the Tier-1 workflow.",
        "Run exact Tier-1 native-connector cases with independently verified outcomes and cleanup.",
        21,
        "Atlassian, Bitbucket, and Microsoft 365 test identities, permissions, and fixtures.",
    ),
    Seed(
        112,
        "Todo",
        "Build",
        "Idea",
        "Support governed corporate proxy and enterprise-CA connectivity without broadening provider origins or leaking credentials.",
        "A typed provider read succeeds through an authenticated proxy and TLS-inspection path with bounded diagnostics.",
        21,
        "Representative corporate proxy and enterprise CA test environment.",
    ),
    Seed(
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
    View(
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
    View(
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
    View(
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
    View(
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
    View(
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


class Gh:
    """Typed subprocess wrapper for GitHub CLI."""

    def __init__(self) -> None:
        executable = shutil.which("gh")
        if executable is None:
            raise BootstrapError("GitHub CLI is missing. Install `gh` and rerun.")
        self.executable = executable

    def run(
        self,
        *args: str,
        input_text: str | None = None,
        allow_duplicate: bool = False,
    ) -> str:
        """Run ``gh`` and return standard output."""

        process = subprocess.run(
            [self.executable, *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode == 0:
            return process.stdout
        detail = (process.stderr or process.stdout).strip()
        lowered = detail.casefold()
        if allow_duplicate and (
            "already exists" in lowered or "already added" in lowered
        ):
            return ""
        raise BootstrapError(f"gh {' '.join(args)} failed: {detail[:2000]}")

    def json(self, *args: str, input_text: str | None = None) -> dict[str, Any]:
        """Run ``gh`` and decode a JSON object."""

        try:
            value = json.loads(self.run(*args, input_text=input_text))
        except json.JSONDecodeError as exc:
            raise BootstrapError("GitHub CLI returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise BootstrapError("GitHub CLI returned an unexpected JSON value.")
        return value

    def graphql(
        self, query: str, variables: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Run a GraphQL query or mutation through ``gh api``."""

        payload = json.dumps({"query": query, "variables": dict(variables)})
        response = self.json(
            "api", "graphql", "--input", "-", input_text=payload
        )
        if response.get("errors"):
            raise BootstrapError(json.dumps(response["errors"], ensure_ascii=False))
        data = response.get("data")
        if not isinstance(data, dict):
            raise BootstrapError("GraphQL response has no data object.")
        return data


def parse_project_list(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract project records from ``gh project list`` JSON."""

    projects = raw.get("projects")
    if not isinstance(projects, list):
        raise BootstrapError("Could not parse `gh project list` output.")
    return [item for item in projects if isinstance(item, dict)]


def ensure_project(gh: Gh, owner: str) -> tuple[int, str, bool]:
    """Create or reuse the exact private project."""

    projects = parse_project_list(
        gh.json(
            "project",
            "list",
            "--owner",
            owner,
            "--limit",
            "100",
            "--format",
            "json",
        )
    )
    matches = [item for item in projects if item.get("title") == TITLE]
    if len(matches) > 1:
        raise BootstrapError(f"Multiple projects are named {TITLE!r}.")
    created = not matches
    if created:
        project = gh.json(
            "project",
            "create",
            "--owner",
            owner,
            "--title",
            TITLE,
            "--format",
            "json",
        )
        print(f"[create] {TITLE}")
    else:
        project = matches[0]
        print(f"[reuse] {TITLE}")
    number = int(project["number"])
    gh.run(
        "project",
        "edit",
        str(number),
        "--owner",
        owner,
        "--title",
        TITLE,
        "--description",
        DESCRIPTION,
        "--readme",
        README,
        "--visibility",
        "PRIVATE",
    )
    project_id = gh.run(
        "project",
        "view",
        str(number),
        "--owner",
        owner,
        "--format",
        "json",
        "--jq",
        ".id",
    ).strip()
    if not project_id:
        raise BootstrapError("Could not resolve the project node ID.")
    return number, project_id, created


def ensure_fields(gh: Gh, number: int, owner: str) -> None:
    """Create every missing custom field."""

    raw = gh.json(
        "project", "field-list", str(number), "--owner", owner, "--format", "json"
    )
    fields = raw.get("fields")
    if not isinstance(fields, list):
        raise BootstrapError("Could not parse project fields.")
    names = {item.get("name") for item in fields if isinstance(item, dict)}
    for field in FIELDS:
        if field.name in names:
            print(f"[reuse] field: {field.name}")
            continue
        args = [
            "project",
            "field-create",
            str(number),
            "--owner",
            owner,
            "--name",
            field.name,
            "--data-type",
            field.data_type,
        ]
        if field.options:
            args.extend(("--single-select-options", ",".join(field.options)))
        gh.run(*args)
        print(f"[create] field: {field.name}")


def set_item(gh: Gh, number: int, owner: str, seed: Seed) -> None:
    """Add one issue and set its operating metadata."""

    gh.run(
        "project",
        "item-add",
        str(number),
        "--owner",
        owner,
        "--url",
        seed.url,
        allow_duplicate=True,
    )
    values = {
        "Status": ("value", seed.status),
        "Outcome": ("text", seed.outcome),
        "Project": ("value", "MasterAgent"),
        "Stage": ("value", seed.stage),
        "Evidence level": ("value", seed.evidence),
        "Next validation": ("text", seed.validation),
        "User impact": ("value", "Expected"),
        "WIP owner": ("text", "Rory"),
        "Review date": (
            "date",
            (date.today() + timedelta(days=seed.review_days)).isoformat(),
        ),
    }
    if seed.dependency:
        values["External dependency"] = ("text", seed.dependency)
    for field, (kind, value) in values.items():
        flag = {"value": "--value", "text": "--text", "date": "--date"}[kind]
        gh.run(
            "project",
            "item-edit",
            str(number),
            "--owner",
            owner,
            "--url",
            seed.url,
            "--field",
            field,
            flag,
            value,
        )
    print(f"[seed] MasterAgent#{seed.number}")


DETAILS_QUERY: Final = """
query($id: ID!) {
  node(id: $id) {
    ... on ProjectV2 {
      fields(first: 100) {
        nodes { ... on ProjectV2FieldCommon { id name } }
      }
      views(first: 100) { nodes { id name } }
    }
  }
}
"""
CREATE_VIEW: Final = """
mutation($input: CreateProjectV2ViewInput!) {
  createProjectV2View(input: $input) { projectV2View { id name } }
}
"""
UPDATE_VIEW: Final = """
mutation($input: UpdateProjectV2ViewInput!) {
  updateProjectV2View(input: $input) { projectV2View { id name filter } }
}
"""


def ensure_views(gh: Gh, project_id: str) -> None:
    """Create or reconcile the five saved operating views."""

    node = gh.graphql(DETAILS_QUERY, {"id": project_id}).get("node")
    if not isinstance(node, dict):
        raise BootstrapError("Could not query project fields and views.")
    field_nodes = node.get("fields", {}).get("nodes", [])
    view_nodes = node.get("views", {}).get("nodes", [])
    field_ids = {
        item["name"]: item["id"]
        for item in field_nodes
        if isinstance(item, dict) and item.get("name") and item.get("id")
    }
    views = {
        item["name"]: item
        for item in view_nodes
        if isinstance(item, dict) and item.get("name") and item.get("id")
    }
    desired_names = {view.name for view in VIEWS}
    default_candidates = [
        item
        for item in view_nodes
        if isinstance(item, dict) and item.get("name") not in desired_names
    ]

    for spec in VIEWS:
        missing = [name for name in spec.fields if name not in field_ids]
        if missing:
            raise BootstrapError("View fields are missing: " + ", ".join(missing))
        visible = [field_ids[name] for name in spec.fields]
        current = views.get(spec.name)
        if current is None and spec.name == "Now" and len(default_candidates) == 1:
            current = default_candidates[0]
        if current is None:
            result = gh.graphql(
                CREATE_VIEW,
                {
                    "input": {
                        "projectId": project_id,
                        "name": spec.name,
                        "layout": "TABLE_LAYOUT",
                        "configuration": {"visibleFieldIds": visible},
                    }
                },
            )
            current = result["createProjectV2View"]["projectV2View"]
            print(f"[create] view: {spec.name}")
        gh.graphql(
            UPDATE_VIEW,
            {
                "input": {
                    "viewId": current["id"],
                    "name": spec.name,
                    "layout": "TABLE_LAYOUT",
                    "filter": spec.query,
                    "configuration": {"visibleFieldIds": visible},
                }
            },
        )
        print(f"[set] view: {spec.name}")


def enforce_wip(gh: Gh, number: int, owner: str) -> int:
    """Fail when the project has more than three active outcomes."""

    raw = gh.json(
        "project",
        "item-list",
        str(number),
        "--owner",
        owner,
        "--query",
        'status:"In Progress"',
        "--limit",
        "1000",
        "--format",
        "json",
    )
    items = raw.get("items")
    if not isinstance(items, list):
        raise BootstrapError("Could not count active project items.")
    count = len(items)
    if count > MAX_WIP:
        raise BootstrapError(
            f"WIP limit violated: {count} items are In Progress; maximum is {MAX_WIP}."
        )
    return count


def preflight(gh: Gh, owner: str) -> None:
    """Verify authentication, account identity, and Projects scope."""

    gh.run("auth", "status", "--hostname", "github.com")
    login = gh.run("api", "user", "--jq", ".login").strip()
    if login.casefold() != owner.casefold():
        raise BootstrapError(f"gh is authenticated as {login!r}, not {owner!r}.")
    try:
        gh.run(
            "project", "list", "--owner", owner, "--limit", "1", "--format", "json"
        )
    except BootstrapError as exc:
        raise BootstrapError(
            "GitHub Projects access failed. Run once:\n"
            "  gh auth refresh --hostname github.com --scopes project\n"
            f"Original error: {exc}"
        ) from exc


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=f"Create or reconcile {TITLE!r}.")
    parser.add_argument("--owner", default=OWNER)
    parser.add_argument(
        "--refresh-seed",
        action="store_true",
        help="Reapply the initial metadata to seeded issues in an existing project.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Only check that the project has at most three active outcomes.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Create, seed, and validate the operating project."""

    args = parse_args(sys.argv[1:] if argv is None else argv)
    gh = Gh()
    preflight(gh, args.owner)
    number, project_id, created = ensure_project(gh, args.owner)
    if args.audit_only:
        count = enforce_wip(gh, number, args.owner)
        print(f"[ok] WIP {count}/{MAX_WIP}")
        return 0
    ensure_fields(gh, number, args.owner)
    if created or args.refresh_seed:
        for seed in SEEDS:
            set_item(gh, number, args.owner, seed)
    else:
        print("[skip] seed metadata already exists; use --refresh-seed to reapply it")
    ensure_views(gh, project_id)
    count = enforce_wip(gh, number, args.owner)
    url = gh.run(
        "project",
        "view",
        str(number),
        "--owner",
        args.owner,
        "--format",
        "json",
        "--jq",
        ".url",
    ).strip()
    print(f"[done] WIP {count}/{MAX_WIP}: {url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        raise SystemExit(130)
