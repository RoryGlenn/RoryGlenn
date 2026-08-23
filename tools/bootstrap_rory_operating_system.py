#!/usr/bin/env python3
"""Create Rory's private cross-repository GitHub Projects operating board."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from typing import Any, Final, Mapping, Sequence

TITLE: Final = "Rory Operating System"
DESCRIPTION: Final = (
    "Cross-repository operating system for limiting work in progress, "
    "forcing validation, and measuring real user impact."
)
README: Final = """# Rory Operating System

This project controls AI-amplified work across repositories. It optimizes for
verified outcomes rather than the volume of code, issues, documents, or agents.

## Rules

1. **Now contains at most three outcomes.** A fourth item cannot enter
   `In Progress` until another leaves.
2. Every item states an **Outcome** and a falsifiable **Next validation**.
3. Evidence advances through `Idea -> Mocked -> Integrated -> Real environment
   -> Real user`.
4. Technical completion is not completion while user impact is unverified.
5. Review blocked work and kill candidates weekly.
6. Prefer one complete workflow over broader capability count.
"""
MAX_WIP: Final = 3

# name -> (data type, single-select options)
FIELDS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "Outcome": ("TEXT", ()),
    "Project": (
        "SINGLE_SELECT",
        ("MasterAgent", "LineLight", "commitment-issues", "BranchBeacon", "Other"),
    ),
    "Stage": (
        "SINGLE_SELECT",
        ("Diagnose", "Build", "Validate", "Ship", "Measure", "Maintain", "Kill"),
    ),
    "Evidence level": (
        "SINGLE_SELECT",
        ("Idea", "Mocked", "Integrated", "Real environment", "Real user"),
    ),
    "Next validation": ("TEXT", ()),
    "User impact": ("SINGLE_SELECT", ("None", "Expected", "Observed")),
    "WIP owner": ("TEXT", ()),
    "Review date": ("DATE", ()),
    "External dependency": ("TEXT", ()),
}

SEEDS: Final[tuple[dict[str, Any], ...]] = (
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 171,
        "Status": "In Progress",
        "Project": "MasterAgent",
        "Stage": "Diagnose",
        "Evidence level": "Idea",
        "Outcome": "Select one to three Tier-1 employee workflows with exact value, reliability, latency, interaction, and recovery objectives.",
        "Next validation": "Approve bounded workflow specifications that issue #172 can execute unchanged on a managed workstation.",
        "review_days": 7,
    },
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 164,
        "Status": "In Progress",
        "Project": "MasterAgent",
        "Stage": "Build",
        "Evidence level": "Idea",
        "Outcome": "Measure governance, connector initialization, credentials, provider calls, verification, and user interaction separately.",
        "Next validation": "One deterministic benchmark emits stage timings and counts while proving unselected providers remain untouched.",
        "review_days": 14,
    },
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 170,
        "Status": "In Progress",
        "Project": "MasterAgent",
        "Stage": "Build",
        "Evidence level": "Idea",
        "Outcome": "Bind the exact native connector implementation into execution, approval, audit, diagnostics, and performance identity.",
        "Next validation": "Adversarial tests reject implementation drift before connector construction and prove no fallback occurs.",
        "review_days": 14,
    },
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 172,
        "Status": "Todo",
        "Project": "MasterAgent",
        "Stage": "Validate",
        "Evidence level": "Integrated",
        "Outcome": "Prove the Tier-1 workflow is reliable and usable on a representative managed Windows workstation.",
        "Next validation": "Run identical baseline and post-change workloads and issue a ready, ready_with_restrictions, or not_ready recommendation.",
        "External dependency": "Issues #171, #164, and #170 plus a representative managed Windows 11 environment.",
        "review_days": 28,
    },
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 94,
        "Status": "Todo",
        "Project": "MasterAgent",
        "Stage": "Validate",
        "Evidence level": "Integrated",
        "Outcome": "Provide protected credentials and stable non-production fixtures for every provider required by the Tier-1 workflow.",
        "Next validation": "Run the exact Tier-1 native-connector cases with independently verified outcomes and cleanup.",
        "External dependency": "Atlassian, Bitbucket, and Microsoft 365 test identities, permissions, and fixtures.",
        "review_days": 21,
    },
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 112,
        "Status": "Todo",
        "Project": "MasterAgent",
        "Stage": "Build",
        "Evidence level": "Idea",
        "Outcome": "Support governed corporate proxy and enterprise-CA connectivity without broadening provider origins or leaking credentials.",
        "Next validation": "A typed provider read succeeds through an authenticated proxy and TLS-inspection path with bounded diagnostics.",
        "External dependency": "Representative corporate proxy and enterprise CA test environment.",
        "review_days": 21,
    },
    {
        "repo": "RoryGlenn/MasterAgent",
        "number": 106,
        "Status": "Todo",
        "Project": "MasterAgent",
        "Stage": "Validate",
        "Evidence level": "Idea",
        "Outcome": "Continuously certify the installed MasterAgent artifact as a standard non-administrator user on Windows 11.",
        "Next validation": "Protected Windows certification runs from a clean installed artifact and fails when required native invariants are skipped.",
        "External dependency": "Protected standard-user Windows 11 runner or VM.",
        "review_days": 28,
    },
)

VIEW_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "Now": (
        "Title", "Status", "Project", "Stage", "Outcome", "Next validation",
        "Evidence level", "User impact", "WIP owner", "Review date",
    ),
    "Validation required": (
        "Title", "Status", "Project", "Stage", "Evidence level",
        "Next validation", "External dependency", "Review date",
    ),
    "Externally blocked": (
        "Title", "Status", "Project", "External dependency",
        "Next validation", "Review date",
    ),
    "Maintenance": (
        "Title", "Status", "Project", "User impact", "Next validation", "Review date",
    ),
    "Kill candidates": (
        "Title", "Status", "Project", "Outcome", "User impact",
        "Next validation", "Review date",
    ),
}

PROJECTS_QUERY = """query($login:String!){user(login:$login){id projectsV2(first:100){nodes{id number title url}}}}"""
CREATE_PROJECT = """mutation($input:CreateProjectV2Input!){createProjectV2(input:$input){projectV2{id number title url}}}"""
DETAILS_QUERY = """query($id:ID!){node(id:$id){... on ProjectV2{id number title url viewerCanUpdate fields(first:100){nodes{__typename ... on ProjectV2FieldCommon{id name dataType} ... on ProjectV2SingleSelectField{options{id name}}}} views(first:100){nodes{id name layout filter}}}}}"""
ITEMS_QUERY = """query($id:ID!){node(id:$id){... on ProjectV2{items(first:100){nodes{id content{__typename ... on Issue{id url title} ... on PullRequest{id url title} ... on DraftIssue{id title}} fieldValues(first:50){nodes{__typename ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}} ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}} ... on ProjectV2ItemFieldDateValue{date field{... on ProjectV2FieldCommon{name}}}}}}}}}"""
ADD_ITEM = """mutation($input:AddProjectV2ItemByIdInput!){addProjectV2ItemById(input:$input){item{id}}}"""
CREATE_VIEW = """mutation($input:CreateProjectV2ViewInput!){createProjectV2View(input:$input){projectV2View{id name}}}"""
UPDATE_VIEW = """mutation($input:UpdateProjectV2ViewInput!){updateProjectV2View(input:$input){projectV2View{id name}}}"""
VIEWER_QUERY = "query{viewer{login}}"


class BootstrapError(RuntimeError):
    """Safe operator-facing bootstrap failure."""


def norm(value: str) -> str:
    return " ".join(value.casefold().split())


def run_gh(*args: str, stdin: str | None = None) -> str:
    executable = shutil.which("gh")
    if executable is None:
        raise BootstrapError("GitHub CLI `gh` is not installed.")
    result = subprocess.run(
        [executable, *args], input=stdin, text=True, capture_output=True, check=False
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown GitHub CLI error").strip()
        raise BootstrapError(f"gh {' '.join(args)} failed: {detail[:2000]}")
    return result.stdout


def graphql(query: str, variables: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": dict(variables or {})})
    response = json.loads(run_gh("api", "graphql", "--input", "-", stdin=payload))
    if response.get("errors"):
        raise BootstrapError(json.dumps(response["errors"], ensure_ascii=False))
    data = response.get("data")
    if not isinstance(data, dict):
        raise BootstrapError("GitHub GraphQL response did not contain data.")
    return data


def project_details(project_id: str) -> dict[str, Any]:
    node = graphql(DETAILS_QUERY, {"id": project_id}).get("node")
    if not isinstance(node, dict) or not node.get("viewerCanUpdate"):
        raise BootstrapError("The authenticated account cannot update the project.")
    return node


def field_map(project_id: str) -> dict[str, dict[str, Any]]:
    nodes = project_details(project_id)["fields"]["nodes"]
    return {node["name"]: node for node in nodes if isinstance(node, dict) and node.get("name")}


def ensure_project(owner: str, title: str) -> dict[str, Any]:
    data = graphql(PROJECTS_QUERY, {"login": owner})
    user = data.get("user")
    if not isinstance(user, dict):
        raise BootstrapError(f"GitHub user {owner!r} was not found.")
    matches = [p for p in user["projectsV2"]["nodes"] if p["title"] == title]
    if len(matches) > 1:
        raise BootstrapError(f"Multiple projects are named {title!r}.")
    if matches:
        project = matches[0]
        print(f"[reuse] project #{project['number']}: {title}")
    else:
        project = graphql(
            CREATE_PROJECT, {"input": {"ownerId": user["id"], "title": title}}
        )["createProjectV2"]["projectV2"]
        print(f"[create] project #{project['number']}: {title}")
    run_gh(
        "project", "edit", str(project["number"]), "--owner", owner,
        "--title", title, "--description", DESCRIPTION, "--readme", README,
        "--visibility", "PRIVATE",
    )
    return project


def ensure_fields(owner: str, project: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    project_id, number = str(project["id"]), str(project["number"])
    fields = field_map(project_id)
    for name, (data_type, options) in FIELDS.items():
        current = fields.get(name)
        if current is None:
            args = [
                "project", "field-create", number, "--owner", owner,
                "--name", name, "--data-type", data_type,
            ]
            if options:
                args.extend(("--single-select-options", ",".join(options)))
            run_gh(*args)
            print(f"[create] field: {name}")
            fields = field_map(project_id)
            current = fields[name]
        if current.get("dataType") != data_type:
            raise BootstrapError(
                f"Field {name!r} has type {current.get('dataType')!r}; expected {data_type}."
            )
        if options:
            actual = {norm(o["name"]) for o in current.get("options", [])}
            missing = [option for option in options if norm(option) not in actual]
            if missing:
                raise BootstrapError(
                    f"Field {name!r} is missing options {missing!r}; add them in GitHub and rerun."
                )
    missing = {"Title", "Status", *FIELDS} - fields.keys()
    if missing:
        raise BootstrapError("Missing required fields: " + ", ".join(sorted(missing)))
    return fields


def item_values(item: Mapping[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in item["fieldValues"]["nodes"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("field"), dict):
            continue
        name = raw["field"].get("name")
        if not isinstance(name, str):
            continue
        for key in ("name", "text", "date"):
            value = raw.get(key)
            if isinstance(value, str):
                values[name] = value
                break
    return values


def project_items(project_id: str) -> list[dict[str, Any]]:
    node = graphql(ITEMS_QUERY, {"id": project_id}).get("node")
    if not isinstance(node, dict):
        raise BootstrapError("Could not read project items.")
    return [item for item in node["items"]["nodes"] if isinstance(item, dict)]


def select_name(field: Mapping[str, Any], desired: str) -> str:
    matches = [
        option["name"] for option in field.get("options", [])
        if norm(str(option.get("name", ""))) == norm(desired)
    ]
    if len(matches) != 1:
        raise BootstrapError(f"No unique {desired!r} option exists in {field.get('name')!r}.")
    return str(matches[0])


def set_field(
    owner: str,
    project: Mapping[str, Any],
    fields: Mapping[str, Mapping[str, Any]],
    issue_url: str,
    field_name: str,
    value: str,
) -> None:
    field = fields[field_name]
    args = [
        "project", "item-edit", str(project["number"]), "--owner", owner,
        "--url", issue_url, "--field", field_name,
    ]
    data_type = field.get("dataType")
    if data_type == "SINGLE_SELECT":
        args.extend(("--value", select_name(field, value)))
    elif data_type == "DATE":
        args.extend(("--date", value))
    elif data_type == "TEXT":
        args.extend(("--text", value))
    else:
        raise BootstrapError(f"Unsupported data type {data_type!r} for {field_name!r}.")
    run_gh(*args)


def seed_issues(
    owner: str,
    project: Mapping[str, Any],
    fields: Mapping[str, Mapping[str, Any]],
    refresh: bool,
) -> None:
    project_id = str(project["id"])
    existing = {
        item["content"]["url"]: item
        for item in project_items(project_id)
        if isinstance(item.get("content"), dict) and item["content"].get("url")
    }
    today = date.today()
    for seed in SEEDS:
        url = f"https://github.com/{seed['repo']}/issues/{seed['number']}"
        item = existing.get(url)
        is_new = item is None
        if is_new:
            owner_name, repo_name = str(seed["repo"]).split("/", 1)
            issue = json.loads(run_gh("api", f"repos/{owner_name}/{repo_name}/issues/{seed['number']}"))
            if issue.get("pull_request") or not issue.get("node_id"):
                raise BootstrapError(f"{url} is not a resolvable issue.")
            graphql(ADD_ITEM, {"input": {"projectId": project_id, "contentId": issue["node_id"]}})
            print(f"[add] {url}")
        else:
            print(f"[reuse] {url}")
        if not is_new and not refresh:
            continue
        values = {
            key: str(value)
            for key, value in seed.items()
            if key not in {"repo", "number", "review_days"}
        }
        values.setdefault("User impact", "Expected")
        values.setdefault("WIP owner", "Rory")
        values["Review date"] = (
            today + timedelta(days=int(seed.get("review_days", 14)))
        ).isoformat()
        for field_name, value in values.items():
            set_field(owner, project, fields, url, field_name, value)
        print(f"[set] metadata for {seed['repo']}#{seed['number']}")


def ensure_views(project_id: str, fields: Mapping[str, Mapping[str, Any]]) -> None:
    details = project_details(project_id)
    views = [view for view in details["views"]["nodes"] if isinstance(view, dict)]
    by_name = {view["name"]: view for view in views}
    in_progress = select_name(fields["Status"], "In Progress")
    filters = {
        "Now": f'status:"{in_progress}"',
        "Validation required": 'stage:Validate -evidence-level:"Real user" -status:Done',
        "Externally blocked": "has:external-dependency -status:Done",
        "Maintenance": "stage:Maintain -status:Done",
        "Kill candidates": "stage:Kill -status:Done",
    }
    spare = [view for view in views if view["name"] not in VIEW_FIELDS]
    for name, visible_names in VIEW_FIELDS.items():
        view = by_name.get(name)
        if view is None and name == "Now" and len(spare) == 1:
            view = spare[0]
        visible_ids = [str(fields[field_name]["id"]) for field_name in visible_names]
        if view is None:
            view = graphql(
                CREATE_VIEW,
                {"input": {
                    "projectId": project_id,
                    "name": name,
                    "layout": "TABLE_LAYOUT",
                    "configuration": {"visibleFieldIds": visible_ids},
                }},
            )["createProjectV2View"]["projectV2View"]
            print(f"[create] view: {name}")
        graphql(
            UPDATE_VIEW,
            {"input": {
                "viewId": view["id"],
                "name": name,
                "layout": "TABLE_LAYOUT",
                "filter": filters[name],
                "configuration": {"visibleFieldIds": visible_ids},
            }},
        )


def audit_wip(project_id: str) -> list[str]:
    active: list[str] = []
    for item in project_items(project_id):
        if norm(item_values(item).get("Status", "")) != norm("In Progress"):
            continue
        content = item.get("content")
        active.append(str(content.get("title") if isinstance(content, dict) else item["id"]))
    if len(active) > MAX_WIP:
        raise BootstrapError(
            f"WIP limit violated: {len(active)} active outcomes; maximum is {MAX_WIP}."
        )
    return active


def preflight(owner: str) -> None:
    run_gh("auth", "status", "--hostname", "github.com")
    viewer = graphql(VIEWER_QUERY)["viewer"]["login"]
    if norm(viewer) != norm(owner):
        raise BootstrapError(f"GitHub CLI is authenticated as {viewer!r}, not {owner!r}.")
    try:
        graphql(PROJECTS_QUERY, {"login": owner})
    except BootstrapError as exc:
        raise BootstrapError(
            "Authorize GitHub Projects once with `gh auth refresh -s project`, then rerun."
        ) from exc


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Create or reconcile {TITLE!r}.")
    parser.add_argument("--owner", default="RoryGlenn")
    parser.add_argument("--title", default=TITLE)
    parser.add_argument("--refresh-seed", action="store_true")
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    preflight(args.owner)
    data = graphql(PROJECTS_QUERY, {"login": args.owner})
    matches = [
        project for project in data["user"]["projectsV2"]["nodes"]
        if project["title"] == args.title
    ]
    if args.audit_only:
        if len(matches) != 1:
            raise BootstrapError("Audit mode requires exactly one matching existing project.")
        project = matches[0]
    else:
        project = ensure_project(args.owner, args.title)
        fields = ensure_fields(args.owner, project)
        if not args.no_seed:
            seed_issues(args.owner, project, fields, args.refresh_seed)
        ensure_views(str(project["id"]), fields)
    active = audit_wip(str(project["id"]))
    print(f"[ok] WIP limit: {len(active)}/{MAX_WIP}")
    for title in active:
        print(f"  - {title}")
    print(project["url"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BootstrapError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        raise SystemExit(130)
