"""GitHub GraphQL adapter for the Rory Operating System project."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from rory_operating_system_data import (
    DESCRIPTION,
    FIELDS,
    MAX_WIP,
    README,
    SEEDS,
    TITLE,
    VIEWS,
    FieldSpec,
)


class ProjectError(RuntimeError):
    """Raised when the project cannot be reconciled safely."""


@dataclass(frozen=True)
class FieldInfo:
    """Resolved GitHub Project field metadata."""

    id: str
    name: str
    data_type: str
    options: Mapping[str, str]


@dataclass(frozen=True)
class ProjectInfo:
    """Resolved GitHub Project identity."""

    id: str
    number: int
    url: str
    created: bool


class Gh:
    """Small, bounded wrapper around the GitHub CLI."""

    def __init__(self) -> None:
        executable = shutil.which("gh")
        if executable is None:
            raise ProjectError("GitHub CLI is missing. Install `gh` and rerun.")
        self.executable = executable

    def run(self, *args: str, input_text: str | None = None) -> str:
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
        raise ProjectError(f"gh {' '.join(args)} failed: {detail[:2000]}")

    def graphql(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        """Execute one GraphQL operation through ``gh api``."""

        payload = json.dumps({"query": query, "variables": dict(variables)})
        try:
            response = json.loads(
                self.run("api", "graphql", "--input", "-", input_text=payload)
            )
        except json.JSONDecodeError as exc:
            raise ProjectError("GitHub returned malformed GraphQL JSON.") from exc
        if not isinstance(response, dict):
            raise ProjectError("GitHub returned an unexpected GraphQL value.")
        errors = response.get("errors")
        if errors:
            raise ProjectError(json.dumps(errors, ensure_ascii=False)[:4000])
        data = response.get("data")
        if not isinstance(data, dict):
            raise ProjectError("GitHub returned no GraphQL data object.")
        return data


ACCOUNT_QUERY = """
query($login: String!) {
  viewer { login }
  user(login: $login) {
    id
    projectsV2(first: 100) {
      nodes { id number title url public closed }
    }
  }
}
"""

CREATE_PROJECT = """
mutation($input: CreateProjectV2Input!) {
  createProjectV2(input: $input) {
    projectV2 { id number title url public closed }
  }
}
"""

UPDATE_PROJECT = """
mutation($input: UpdateProjectV2Input!) {
  updateProjectV2(input: $input) {
    projectV2 { id number title url public closed }
  }
}
"""

STRUCTURE_QUERY = """
query($id: ID!) {
  node(id: $id) {
    ... on ProjectV2 {
      fields(first: 100) {
        nodes {
          ... on ProjectV2FieldCommon { id name dataType }
          ... on ProjectV2SingleSelectField { options { id name } }
        }
      }
      views(first: 100) { nodes { id name } }
    }
  }
}
"""

CREATE_FIELD = """
mutation($input: CreateProjectV2FieldInput!) {
  createProjectV2Field(input: $input) {
    projectV2Field {
      ... on ProjectV2FieldCommon { id name dataType }
      ... on ProjectV2SingleSelectField { options { id name } }
    }
  }
}
"""

ISSUE_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) { id url title }
  }
}
"""

ITEMS_QUERY = """
query($id: ID!, $after: String) {
  node(id: $id) {
    ... on ProjectV2 {
      items(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue {
              id
              url
              number
              repository { nameWithOwner }
            }
          }
          fieldValues(first: 50) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                optionId
                field { ... on ProjectV2FieldCommon { id name } }
              }
            }
          }
        }
      }
    }
  }
}
"""

ADD_ITEM = """
mutation($input: AddProjectV2ItemByIdInput!) {
  addProjectV2ItemById(input: $input) { item { id } }
}
"""

UPDATE_ITEM_FIELD = """
mutation($input: UpdateProjectV2ItemFieldValueInput!) {
  updateProjectV2ItemFieldValue(input: $input) { projectV2Item { id } }
}
"""

CREATE_VIEW = """
mutation($input: CreateProjectV2ViewInput!) {
  createProjectV2View(input: $input) { projectV2View { id name } }
}
"""

UPDATE_VIEW = """
mutation($input: UpdateProjectV2ViewInput!) {
  updateProjectV2View(input: $input) { projectV2View { id name filter } }
}
"""


def preflight(gh: Gh, owner: str) -> None:
    """Verify authentication, identity, and Projects access."""

    gh.run("auth", "status", "--hostname", "github.com")
    try:
        data = gh.graphql(ACCOUNT_QUERY, {"login": owner})
    except ProjectError as exc:
        raise ProjectError(
            "GitHub Projects access failed. Run once:\n"
            "  gh auth refresh --hostname github.com --scopes project\n"
            f"Original error: {exc}"
        ) from exc
    viewer = data.get("viewer")
    login = viewer.get("login") if isinstance(viewer, dict) else None
    if not isinstance(login, str) or login.casefold() != owner.casefold():
        raise ProjectError(f"gh is authenticated as {login!r}, not {owner!r}.")
    if not isinstance(data.get("user"), dict):
        raise ProjectError(f"GitHub user {owner!r} was not found.")


def ensure_project(gh: Gh, owner: str) -> ProjectInfo:
    """Create or reuse the exact private user-level project."""

    data = gh.graphql(ACCOUNT_QUERY, {"login": owner})
    user = data.get("user")
    if not isinstance(user, dict) or not isinstance(user.get("id"), str):
        raise ProjectError(f"Could not resolve GitHub user {owner!r}.")
    connection = user.get("projectsV2")
    nodes = connection.get("nodes") if isinstance(connection, dict) else None
    if not isinstance(nodes, list):
        raise ProjectError("Could not list GitHub Projects.")
    matches = [
        node
        for node in nodes
        if isinstance(node, dict) and node.get("title") == TITLE
    ]
    if len(matches) > 1:
        raise ProjectError(f"Multiple projects are named {TITLE!r}.")
    created = not matches
    if created:
        result = gh.graphql(
            CREATE_PROJECT,
            {"input": {"ownerId": user["id"], "title": TITLE}},
        )
        project = result.get("createProjectV2", {}).get("projectV2")
        print(f"[create] {TITLE}")
    else:
        project = matches[0]
        print(f"[reuse] {TITLE}")
    if not isinstance(project, dict) or not isinstance(project.get("id"), str):
        raise ProjectError("Could not resolve the project after creation.")
    updated = gh.graphql(
        UPDATE_PROJECT,
        {
            "input": {
                "projectId": project["id"],
                "title": TITLE,
                "shortDescription": DESCRIPTION,
                "readme": README,
                "public": False,
                "closed": False,
            }
        },
    ).get("updateProjectV2", {}).get("projectV2")
    if not isinstance(updated, dict):
        raise ProjectError("Could not update project metadata.")
    return ProjectInfo(
        id=str(updated["id"]),
        number=int(updated["number"]),
        url=str(updated["url"]),
        created=created,
    )


def _structure(
    gh: Gh, project_id: str
) -> tuple[dict[str, FieldInfo], list[dict[str, str]]]:
    """Return field and view metadata for one project."""

    node = gh.graphql(STRUCTURE_QUERY, {"id": project_id}).get("node")
    if not isinstance(node, dict):
        raise ProjectError("Could not read project fields and views.")
    field_nodes = node.get("fields", {}).get("nodes", [])
    view_nodes = node.get("views", {}).get("nodes", [])
    fields: dict[str, FieldInfo] = {}
    for raw in field_nodes:
        if not isinstance(raw, dict):
            continue
        field_id = raw.get("id")
        name = raw.get("name")
        data_type = raw.get("dataType")
        if not all(
            isinstance(value, str) for value in (field_id, name, data_type)
        ):
            continue
        options: dict[str, str] = {}
        for option in raw.get("options") or []:
            if (
                isinstance(option, dict)
                and isinstance(option.get("id"), str)
                and isinstance(option.get("name"), str)
            ):
                options[option["name"]] = option["id"]
        fields[name] = FieldInfo(field_id, name, data_type, options)
    views = [
        {"id": str(raw["id"]), "name": str(raw["name"])}
        for raw in view_nodes
        if isinstance(raw, dict) and raw.get("id") and raw.get("name")
    ]
    return fields, views


def _option_inputs(options: Sequence[str]) -> list[dict[str, str]]:
    """Build deterministic single-select option inputs."""

    colors = (
        "BLUE",
        "GREEN",
        "PURPLE",
        "ORANGE",
        "YELLOW",
        "PINK",
        "GRAY",
        "RED",
    )
    return [
        {
            "name": name,
            "description": "",
            "color": colors[index % len(colors)],
        }
        for index, name in enumerate(options)
    ]


def _validate_field(existing: FieldInfo, spec: FieldSpec) -> None:
    """Fail closed when an existing field conflicts with the desired schema."""

    if existing.data_type != spec.data_type:
        raise ProjectError(
            f"Field {spec.name!r} has type {existing.data_type}, "
            f"expected {spec.data_type}."
        )
    missing = [option for option in spec.options if option not in existing.options]
    if missing:
        raise ProjectError(
            f"Field {spec.name!r} is missing options: {', '.join(missing)}. "
            "Rename or repair the conflicting field, then rerun."
        )


def ensure_fields(gh: Gh, project_id: str) -> dict[str, FieldInfo]:
    """Create missing fields and validate reused fields."""

    fields, _ = _structure(gh, project_id)
    for spec in FIELDS:
        existing = fields.get(spec.name)
        if existing is not None:
            _validate_field(existing, spec)
            print(f"[reuse] field: {spec.name}")
            continue
        input_value: dict[str, Any] = {
            "projectId": project_id,
            "name": spec.name,
            "dataType": spec.data_type,
        }
        if spec.options:
            input_value["singleSelectOptions"] = _option_inputs(spec.options)
        gh.graphql(CREATE_FIELD, {"input": input_value})
        print(f"[create] field: {spec.name}")
    fields, _ = _structure(gh, project_id)
    required = {"Title", "Status", *(spec.name for spec in FIELDS)}
    missing_names = sorted(required - fields.keys())
    if missing_names:
        raise ProjectError(
            "Required fields are missing: " + ", ".join(missing_names)
        )
    return fields


def _items(gh: Gh, project_id: str) -> list[dict[str, Any]]:
    """Read all project items with bounded pagination."""

    after: str | None = None
    items: list[dict[str, Any]] = []
    for _ in range(100):
        node = gh.graphql(
            ITEMS_QUERY, {"id": project_id, "after": after}
        ).get("node")
        connection = node.get("items") if isinstance(node, dict) else None
        if not isinstance(connection, dict):
            raise ProjectError("Could not read project items.")
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise ProjectError("Project item response is malformed.")
        items.extend(item for item in nodes if isinstance(item, dict))
        page = connection.get("pageInfo")
        if not isinstance(page, dict) or not page.get("hasNextPage"):
            return items
        cursor = page.get("endCursor")
        if not isinstance(cursor, str) or not cursor:
            raise ProjectError("Project item pagination returned no cursor.")
        after = cursor
    raise ProjectError("Project item pagination exceeded 10,000 items.")


def _issue(gh: Gh, number: int) -> dict[str, str]:
    """Resolve one MasterAgent issue node."""

    repository = gh.graphql(
        ISSUE_QUERY,
        {"owner": "RoryGlenn", "name": "MasterAgent", "number": number},
    ).get("repository")
    issue = repository.get("issue") if isinstance(repository, dict) else None
    if not isinstance(issue, dict) or not isinstance(issue.get("id"), str):
        raise ProjectError(f"MasterAgent issue #{number} was not found.")
    return {
        "id": str(issue["id"]),
        "url": str(issue["url"]),
        "title": str(issue["title"]),
    }


def _find_option(field: FieldInfo, name: str) -> str:
    """Resolve one single-select option by exact or case-insensitive name."""

    if name in field.options:
        return field.options[name]
    matches = [
        option_id
        for option_name, option_id in field.options.items()
        if option_name.casefold() == name.casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    raise ProjectError(
        f"Field {field.name!r} has no unique option named {name!r}."
    )


def _set_value(
    gh: Gh,
    project_id: str,
    item_id: str,
    field: FieldInfo,
    *,
    text: str | None = None,
    date_value: str | None = None,
    option: str | None = None,
) -> None:
    """Set one exact Project item field value."""

    selected = sum(value is not None for value in (text, date_value, option))
    if selected != 1:
        raise ProjectError("Exactly one project field value must be supplied.")
    value: dict[str, str]
    if text is not None:
        value = {"text": text}
    elif date_value is not None:
        value = {"date": date_value}
    else:
        value = {"singleSelectOptionId": _find_option(field, str(option))}
    gh.graphql(
        UPDATE_ITEM_FIELD,
        {
            "input": {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field.id,
                "value": value,
            }
        },
    )


def seed_issues(
    gh: Gh,
    project_id: str,
    fields: Mapping[str, FieldInfo],
) -> None:
    """Add and configure the seven initial MasterAgent issues."""

    existing = {
        content["id"]: item["id"]
        for item in _items(gh, project_id)
        if isinstance(item.get("content"), dict)
        and isinstance((content := item["content"]).get("id"), str)
        and isinstance(item.get("id"), str)
    }
    for seed in SEEDS:
        issue = _issue(gh, seed.number)
        item_id = existing.get(issue["id"])
        if item_id is None:
            result = gh.graphql(
                ADD_ITEM,
                {
                    "input": {
                        "projectId": project_id,
                        "contentId": issue["id"],
                    }
                },
            )
            item = result.get("addProjectV2ItemById", {}).get("item")
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ProjectError(f"Could not add MasterAgent#{seed.number}.")
            item_id = item["id"]
        values: dict[str, dict[str, str]] = {
            "Status": {"option": seed.status},
            "Outcome": {"text": seed.outcome},
            "Project": {"option": "MasterAgent"},
            "Stage": {"option": seed.stage},
            "Evidence level": {"option": seed.evidence},
            "Next validation": {"text": seed.validation},
            "User impact": {"option": "Expected"},
            "WIP owner": {"text": "Rory"},
            "Review date": {
                "date_value": (
                    date.today() + timedelta(days=seed.review_days)
                ).isoformat()
            },
        }
        if seed.dependency:
            values["External dependency"] = {"text": seed.dependency}
        for field_name, kwargs in values.items():
            _set_value(
                gh,
                project_id,
                item_id,
                fields[field_name],
                **kwargs,
            )
        print(f"[seed] MasterAgent#{seed.number}")


def ensure_views(
    gh: Gh,
    project_id: str,
    fields: Mapping[str, FieldInfo],
) -> None:
    """Create or reconcile the five saved table views."""

    _, view_nodes = _structure(gh, project_id)
    views = {view["name"]: view for view in view_nodes}
    desired_names = {spec.name for spec in VIEWS}
    unclaimed = [view for view in view_nodes if view["name"] not in desired_names]
    for spec in VIEWS:
        missing = [name for name in spec.fields if name not in fields]
        if missing:
            raise ProjectError("View fields are missing: " + ", ".join(missing))
        visible = [fields[name].id for name in spec.fields]
        current = views.get(spec.name)
        if current is None and spec.name == "Now" and len(unclaimed) == 1:
            current = unclaimed[0]
        if current is None:
            created = gh.graphql(
                CREATE_VIEW,
                {
                    "input": {
                        "projectId": project_id,
                        "name": spec.name,
                        "layout": "TABLE_LAYOUT",
                        "configuration": {"visibleFieldIds": visible},
                    }
                },
            ).get("createProjectV2View", {}).get("projectV2View")
            if not isinstance(created, dict) or not isinstance(
                created.get("id"), str
            ):
                raise ProjectError(f"Could not create view {spec.name!r}.")
            current = {"id": str(created["id"]), "name": spec.name}
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


def count_wip(gh: Gh, project_id: str) -> int:
    """Count items whose Status is In Progress."""

    count = 0
    for item in _items(gh, project_id):
        values = item.get("fieldValues")
        nodes = values.get("nodes") if isinstance(values, dict) else None
        if not isinstance(nodes, list):
            continue
        for value in nodes:
            if not isinstance(value, dict):
                continue
            field = value.get("field")
            field_name = field.get("name") if isinstance(field, dict) else None
            selected = value.get("name")
            if (
                field_name == "Status"
                and isinstance(selected, str)
                and selected.casefold() == "in progress"
            ):
                count += 1
                break
    return count


def enforce_wip(gh: Gh, project_id: str) -> int:
    """Fail when more than three outcomes are active."""

    count = count_wip(gh, project_id)
    if count > MAX_WIP:
        raise ProjectError(
            f"WIP limit violated: {count} items are In Progress; "
            f"maximum is {MAX_WIP}."
        )
    return count
