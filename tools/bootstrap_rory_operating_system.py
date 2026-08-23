#!/usr/bin/env python3
"""Create and maintain Rory's cross-repository GitHub Projects board."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from typing import Any, Final, Mapping, Sequence

TITLE: Final = "Rory Operating System"
MAX_WIP: Final = 3
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

FIELDS: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "Outcome": ("TEXT", ()),
    "Project": ("SINGLE_SELECT", ("MasterAgent", "LineLight", "commitment-issues", "BranchBeacon", "Other")),
    "Stage": ("SINGLE_SELECT", ("Diagnose", "Build", "Validate", "Ship", "Measure", "Maintain", "Kill")),
    "Evidence level": ("SINGLE_SELECT", ("Idea", "Mocked", "Integrated", "Real environment", "Real user")),
    "Next validation": ("TEXT", ()),
    "User impact": ("SINGLE_SELECT", ("None", "Expected", "Observed")),
    "WIP owner": ("TEXT", ()),
    "Review date": ("DATE", ()),
    "External dependency": ("TEXT", ()),
}

SEEDS: Final[tuple[dict[str, Any], ...]] = (
    {"number": 171, "Status": "In Progress", "Project": "MasterAgent", "Stage": "Diagnose", "Evidence level": "Idea", "Outcome": "Select one to three Tier-1 employee workflows with exact value, reliability, latency, interaction, and recovery objectives.", "Next validation": "Approve bounded workflow specifications that issue #172 can execute unchanged on a managed workstation.", "review_days": 7},
    {"number": 164, "Status": "In Progress", "Project": "MasterAgent", "Stage": "Build", "Evidence level": "Idea", "Outcome": "Measure governance, connector initialization, credentials, provider calls, verification, and user interaction separately.", "Next validation": "One deterministic benchmark emits stage timings and counts while proving unselected providers remain untouched.", "review_days": 14},
    {"number": 170, "Status": "In Progress", "Project": "MasterAgent", "Stage": "Build", "Evidence level": "Idea", "Outcome": "Bind the exact native connector implementation into execution, approval, audit, diagnostics, and performance identity.", "Next validation": "Adversarial tests reject implementation drift before connector construction and prove no fallback occurs.", "review_days": 14},
    {"number": 172, "Status": "Todo", "Project": "MasterAgent", "Stage": "Validate", "Evidence level": "Integrated", "Outcome": "Prove the Tier-1 workflow is reliable and usable on a representative managed Windows workstation.", "Next validation": "Run identical baseline and post-change workloads and issue a ready, ready_with_restrictions, or not_ready recommendation.", "External dependency": "Issues #171, #164, and #170 plus a representative managed Windows 11 environment.", "review_days": 28},
    {"number": 94, "Status": "Todo", "Project": "MasterAgent", "Stage": "Validate", "Evidence level": "Integrated", "Outcome": "Provide protected credentials and stable non-production fixtures for every provider required by the Tier-1 workflow.", "Next validation": "Run the exact Tier-1 native-connector cases with independently verified outcomes and cleanup.", "External dependency": "Atlassian, Bitbucket, and Microsoft 365 test identities, permissions, and fixtures.", "review_days": 21},
    {"number": 112, "Status": "Todo", "Project": "MasterAgent", "Stage": "Build", "Evidence level": "Idea", "Outcome": "Support governed corporate proxy and enterprise-CA connectivity without broadening provider origins or leaking credentials.", "Next validation": "A typed provider read succeeds through an authenticated proxy and TLS-inspection path with bounded diagnostics.", "External dependency": "Representative corporate proxy and enterprise CA test environment.", "review_days": 21},
    {"number": 106, "Status": "Todo", "Project": "MasterAgent", "Stage": "Validate", "Evidence level": "Idea", "Outcome": "Continuously certify the installed MasterAgent artifact as a standard non-administrator user on Windows 11.", "Next validation": "Protected Windows certification runs from a clean installed artifact and fails when required native invariants are skipped.", "External dependency": "Protected standard-user Windows 11 runner or VM.", "review_days": 28},
)

VIEW_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "Now": ("Title", "Status", "Project", "Stage", "Outcome", "Next validation", "Evidence level", "User impact", "WIP owner", "Review date"),
    "Validation required": ("Title", "Status", "Project", "Stage", "Evidence level", "Next validation", "External dependency", "Review date"),
    "Externally blocked": ("Title", "Status", "Project", "External dependency", "Next validation", "Review date"),
    "Maintenance": ("Title", "Status", "Project", "User impact", "Next validation", "Review date"),
    "Kill candidates": ("Title", "Status", "Project", "Outcome", "User impact", "Next validation", "Review date"),
}

PROJECTS_QUERY = """query($login:String!){user(login:$login){id projectsV2(first:100){nodes{id number title url}}}}"""
CREATE_PROJECT = """mutation($input:CreateProjectV2Input!){createProjectV2(input:$input){projectV2{id number title url}}}"""
DETAILS_QUERY = """query($id:ID!){node(id:$id){... on ProjectV2{id number title url viewerCanUpdate fields(first:100){nodes{__typename ... on ProjectV2FieldCommon{id name dataType} ... on ProjectV2SingleSelectField{options{id name}}}} views(first:100){nodes{id name layout filter}}}}}"""
ITEMS_QUERY = """query($id:ID!,$after:String){node(id:$id){... on ProjectV2{items(first:100,after:$after){pageInfo{hasNextPage endCursor} nodes{id content{__typename ... on Issue{id url title} ... on PullRequest{id url title} ... on DraftIssue{id title}} fieldValues(first:50){nodes{__typename ... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2FieldCommon{name}}} ... on ProjectV2ItemFieldTextValue{text field{... on ProjectV2FieldCommon{name}}} ... on ProjectV2ItemFieldDateValue{date field{... on ProjectV2FieldCommon{name}}}}}}}}}}"""
ADD_ITEM = """mutation($input:AddProjectV2ItemByIdInput!){addProjectV2ItemById(input:$input){item{id}}}"""
UPDATE_ITEM_FIELD = """mutation($input:UpdateProjectV2ItemFieldValueInput!){updateProjectV2ItemFieldValue(input:$input){projectV2Item{id}}}"""
CREATE_VIEW = """mutation($input:CreateProjectV2ViewInput!){createProjectV2View(input:$input){projectV2View{id name}}}"""
UPDATE_VIEW = """mutation($input:UpdateProjectV2ViewInput!){updateProjectV2View(input:$input){projectV2View{id name}}}"""
VIEWER_QUERY = "query{viewer{login}}"
GRAPHQL_DOCUMENTS = (PROJECTS_QUERY, CREATE_PROJECT, DETAILS_QUERY, ITEMS_QUERY, ADD_ITEM, UPDATE_ITEM_FIELD, CREATE_VIEW, UPDATE_VIEW, VIEWER_QUERY)


class BootstrapError(RuntimeError):
    """Safe operator-facing bootstrap failure."""


def norm(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_graphql_documents() -> None:
    """Catch truncated static GraphQL before any mutation occurs."""

    pairs = {"}": "{", ")": "(", "]": "["}
    for index, document in enumerate(GRAPHQL_DOCUMENTS, start=1):
        stack: list[str] = []
        in_string = escaped = in_comment = False
        for character in document:
            if in_comment:
                in_comment = character != "\n"
            elif in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
            elif character == "#":
                in_comment = True
            elif character == '"':
                in_string = True
            elif character in "{([":
                stack.append(character)
            elif character in "})]":
                if not stack or stack.pop() != pairs[character]:
                    raise BootstrapError(f"GraphQL document {index} has mismatched delimiters.")
        if in_string or stack:
            raise BootstrapError(f"GraphQL document {index} is truncated or unbalanced.")


def run_gh(*args: str, stdin: str | None = None) -> str:
    executable = shutil.which("gh")
    if executable is None:
        raise BootstrapError("GitHub CLI `gh` is not installed.")
    result = subprocess.run([executable, *args], input=stdin, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown GitHub CLI error").strip()
        raise BootstrapError(f"gh {' '.join(args)} failed: {detail[:2000]}")
    return result.stdout


def graphql(query: str, variables: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": dict(variables or {})})
    try:
        response = json.loads(run_gh("api", "graphql", "--input", "-", stdin=payload))
    except json.JSONDecodeError as exc:
        raise BootstrapError("GitHub returned malformed GraphQL JSON.") from exc
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
    return {node["name"]: node for node in project_details(project_id)["fields"]["nodes"] if isinstance(node, dict) and node.get("name")}


def ensure_project(owner: str, title: str) -> dict[str, Any]:
    user = graphql(PROJECTS_QUERY, {"login": owner}).get("user")
    if not isinstance(user, dict):
        raise BootstrapError(f"GitHub user {owner!r} was not found.")
    matches = [project for project in user["projectsV2"]["nodes"] if project["title"] == title]
    if len(matches) > 1:
        raise BootstrapError(f"Multiple projects are named {title!r}.")
    if matches:
        project = matches[0]
        print(f"[reuse] project #{project['number']}: {title}")
    else:
        project = graphql(CREATE_PROJECT, {"input": {"ownerId": user["id"], "title": title}})["createProjectV2"]["projectV2"]
        print(f"[create] project #{project['number']}: {title}")
    run_gh("project", "edit", str(project["number"]), "--owner", owner, "--title", title, "--description", DESCRIPTION, "--readme", README, "--visibility", "PRIVATE")
    return project


def ensure_fields(owner: str, project: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    project_id, number = str(project["id"]), str(project["number"])
    fields = field_map(project_id)
    for name, (data_type, options) in FIELDS.items():
        current = fields.get(name)
        if current is None:
            args = ["project", "field-create", number, "--owner", owner, "--name", name, "--data-type", data_type]
            if options:
                args.extend(("--single-select-options", ",".join(options)))
            run_gh(*args)
            print(f"[create] field: {name}")
            fields = field_map(project_id)
            current = fields[name]
        if current.get("dataType") != data_type:
            raise BootstrapError(f"Field {name!r} has type {current.get('dataType')!r}; expected {data_type}.")
        missing = [option for option in options if norm(option) not in {norm(raw["name"]) for raw in current.get("options", [])}]
        if missing:
            raise BootstrapError(f"Field {name!r} is missing options {missing!r}; add them in GitHub and rerun.")
    missing_names = {"Title", "Status", *FIELDS} - fields.keys()
    if missing_names:
        raise BootstrapError("Missing required fields: " + ", ".join(sorted(missing_names)))
    return fields


def item_values(item: Mapping[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in item.get("fieldValues", {}).get("nodes", []):
        field = raw.get("field") if isinstance(raw, dict) else None
        if not isinstance(field, dict) or not isinstance(field.get("name"), str):
            continue
        for key in ("name", "text", "date"):
            if isinstance(raw.get(key), str):
                values[field["name"]] = raw[key]
                break
    return values


def project_items(project_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    after: str | None = None
    for _ in range(100):
        node = graphql(ITEMS_QUERY, {"id": project_id, "after": after}).get("node")
        connection = node.get("items") if isinstance(node, dict) else None
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise BootstrapError("Could not read project items.")
        items.extend(raw for raw in connection["nodes"] if isinstance(raw, dict))
        page = connection.get("pageInfo", {})
        if not page.get("hasNextPage"):
            return items
        after = page.get("endCursor")
        if not isinstance(after, str) or not after:
            raise BootstrapError("Project item pagination returned no cursor.")
    raise BootstrapError("Project item pagination exceeded 10,000 items.")


def option_id(field: Mapping[str, Any], desired: str) -> str:
    matches = [str(raw["id"]) for raw in field.get("options", []) if raw.get("id") and norm(str(raw.get("name", ""))) == norm(desired)]
    if len(matches) != 1:
        raise BootstrapError(f"No unique {desired!r} option exists in {field.get('name')!r}.")
    return matches[0]


def set_field(project_id: str, item_id: str, field: Mapping[str, Any], value: str) -> None:
    data_type = field.get("dataType")
    encoded = ({"singleSelectOptionId": option_id(field, value)} if data_type == "SINGLE_SELECT" else {"date": value} if data_type == "DATE" else {"text": value} if data_type == "TEXT" else None)
    if encoded is None:
        raise BootstrapError(f"Unsupported data type {data_type!r} for {field.get('name')!r}.")
    graphql(UPDATE_ITEM_FIELD, {"input": {"projectId": project_id, "itemId": item_id, "fieldId": field["id"], "value": encoded}})


def seed_issues(project: Mapping[str, Any], fields: Mapping[str, Mapping[str, Any]], refresh: bool) -> None:
    project_id = str(project["id"])
    existing = {item["content"]["url"]: item for item in project_items(project_id) if isinstance(item.get("content"), dict) and item["content"].get("url")}
    today = date.today()
    for seed in SEEDS:
        url = f"https://github.com/RoryGlenn/MasterAgent/issues/{seed['number']}"
        item = existing.get(url)
        if item is None:
            issue = json.loads(run_gh("api", f"repos/RoryGlenn/MasterAgent/issues/{seed['number']}"))
            if issue.get("pull_request") or not issue.get("node_id"):
                raise BootstrapError(f"{url} is not a resolvable issue.")
            item_id = graphql(ADD_ITEM, {"input": {"projectId": project_id, "contentId": issue["node_id"]}})["addProjectV2ItemById"]["item"]["id"]
            item = {"id": item_id, "content": {"url": url}, "fieldValues": {"nodes": []}}
            print(f"[add] {url}")
        else:
            print(f"[reuse] {url}")
        current = item_values(item)
        values = {key: str(value) for key, value in seed.items() if key not in {"number", "review_days"}}
        values.setdefault("User impact", "Expected")
        values.setdefault("WIP owner", "Rory")
        values["Review date"] = (today + timedelta(days=int(seed.get("review_days", 14)))).isoformat()
        changed = False
        for field_name, value in values.items():
            if not refresh and current.get(field_name):
                continue
            set_field(project_id, str(item["id"]), fields[field_name], value)
            changed = True
        if changed:
            print(f"[set] metadata for MasterAgent#{seed['number']}")


def ensure_views(project_id: str, fields: Mapping[str, Mapping[str, Any]]) -> None:
    views = [view for view in project_details(project_id)["views"]["nodes"] if isinstance(view, dict)]
    by_name = {view["name"]: view for view in views}
    filters = {"Now": 'status:"In Progress"', "Validation required": 'stage:Validate -evidence-level:"Real user" -status:Done', "Externally blocked": "has:external-dependency -status:Done", "Maintenance": "stage:Maintain -status:Done", "Kill candidates": "stage:Kill -status:Done"}
    spare = [view for view in views if view["name"] not in VIEW_FIELDS]
    for name, field_names in VIEW_FIELDS.items():
        view = by_name.get(name)
        if view is None and name == "Now" and len(spare) == 1:
            view = spare[0]
        visible_ids = [str(fields[field_name]["id"]) for field_name in field_names]
        if view is None:
            view = graphql(CREATE_VIEW, {"input": {"projectId": project_id, "name": name, "layout": "TABLE_LAYOUT", "configuration": {"visibleFieldIds": visible_ids}}})["createProjectV2View"]["projectV2View"]
            print(f"[create] view: {name}")
        graphql(UPDATE_VIEW, {"input": {"viewId": view["id"], "name": name, "layout": "TABLE_LAYOUT", "filter": filters[name], "configuration": {"visibleFieldIds": visible_ids}}})
        print(f"[set] view: {name}")


def audit_wip(project_id: str) -> list[str]:
    active: list[str] = []
    for item in project_items(project_id):
        if norm(item_values(item).get("Status", "")) != norm("In Progress"):
            continue
        content = item.get("content")
        active.append(str(content.get("title") if isinstance(content, dict) else item["id"]))
    if len(active) > MAX_WIP:
        raise BootstrapError(f"WIP limit violated: {len(active)} active outcomes; maximum is {MAX_WIP}.")
    return active


def preflight(owner: str) -> None:
    validate_graphql_documents()
    run_gh("auth", "status", "--hostname", "github.com")
    viewer = graphql(VIEWER_QUERY)["viewer"]["login"]
    if norm(viewer) != norm(owner):
        raise BootstrapError(f"GitHub CLI is authenticated as {viewer!r}, not {owner!r}.")
    try:
        graphql(PROJECTS_QUERY, {"login": owner})
    except BootstrapError as exc:
        raise BootstrapError("Authorize GitHub Projects once with `gh auth refresh -s project`, then rerun.") from exc


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Create or reconcile {TITLE!r}.")
    parser.add_argument("--owner", default="RoryGlenn")
    parser.add_argument("--title", default=TITLE)
    parser.add_argument("--refresh-seed", action="store_true")
    parser.add_argument("--no-seed", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--self-check", action="store_true", help="Validate static GraphQL without contacting GitHub.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    validate_graphql_documents()
    if args.self_check:
        print(f"[ok] validated {len(GRAPHQL_DOCUMENTS)} GraphQL documents")
        return 0
    preflight(args.owner)
    data = graphql(PROJECTS_QUERY, {"login": args.owner})
    matches = [project for project in data["user"]["projectsV2"]["nodes"] if project["title"] == args.title]
    if args.audit_only:
        if len(matches) != 1:
            raise BootstrapError("Audit mode requires exactly one matching existing project.")
        project = matches[0]
    else:
        project = ensure_project(args.owner, args.title)
        fields = ensure_fields(args.owner, project)
        if not args.no_seed:
            seed_issues(project, fields, args.refresh_seed)
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
