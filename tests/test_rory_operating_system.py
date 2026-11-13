"""Exercise the documented command with a local GitHub CLI fixture."""

from __future__ import annotations

import contextlib
import copy
from datetime import date, timedelta
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
from typing import Sequence
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bootstrap_rory_operating_system as bootstrap
import rory_operating_system_data as model
import rory_operating_system_github as github


class FixtureGitHub:
    """Serve synthetic GraphQL responses at the subprocess boundary."""

    def __init__(self, *, existing: bool = True) -> None:
        self.project = {
            "id": "PVT_fixture",
            "number": 7,
            "title": model.TITLE,
            "url": "https://github.com/users/RoryGlenn/projects/7",
            "public": False,
            "closed": False,
        }
        self.projects = [self.project] if existing else []
        self.fields = {
            "Title": {"id": "PVTF_title", "name": "Title", "dataType": "TITLE"},
            "Status": {
                "id": "PVTSSF_status",
                "name": "Status",
                "dataType": "SINGLE_SELECT",
                "options": [
                    {"id": "status_todo", "name": "Todo"},
                    {"id": "status_active", "name": "In progress"},
                    {"id": "status_done", "name": "Done"},
                ],
            },
        }
        if existing:
            for spec in model.FIELDS:
                self.add_field(spec.name, spec.data_type, spec.options)
        self.views = [{"id": "PVTV_default", "name": "View 1"}]
        self.items: list[dict] = []
        self.values: dict[tuple[str, str], dict[str, str]] = {}
        self.page_size = 100
        self.commands: list[list[str]] = []
        self.operations: list[tuple[str, dict]] = []

    def add_field(
        self, name: str, data_type: str, options: Sequence[str] = ()
    ) -> dict:
        field_id = f"PVTF_fixture_{len(self.fields)}"
        field = {"id": field_id, "name": name, "dataType": data_type}
        if options:
            field["options"] = [
                {"id": f"{field_id}_option_{index}", "name": option}
                for index, option in enumerate(options)
            ]
        self.fields[name] = field
        return field

    def add_item(self, number: int, status: str = "Todo") -> dict:
        item = {
            "id": f"PVTI_fixture_{number}",
            "content": {
                "id": f"I_fixture_{number}",
                "url": f"https://github.com/RoryGlenn/MasterAgent/issues/{number}",
                "title": f"Fixture issue {number}",
                "number": number,
                "repository": {"nameWithOwner": "RoryGlenn/MasterAgent"},
            },
            "fieldValues": {
                "nodes": [{"name": status, "field": self.fields["Status"]}]
            },
        }
        self.items.append(item)
        return item

    def run(self, args, *, input, **kwargs):
        command = list(args[1:])
        self.commands.append(command)
        if command == ["auth", "status", "--hostname", "github.com"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if command != ["api", "graphql", "--input", "-"]:
            raise AssertionError(f"Unexpected GitHub CLI command {command!r}")
        payload = json.loads(input)
        query = payload["query"]
        variables = payload["variables"]
        self.operations.append((query, variables))
        data = self.respond(query, variables)
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps({"data": data}), stderr=""
        )

    def respond(self, query: str, variables: dict) -> dict:
        if query == github.ACCOUNT_QUERY:
            return {
                "viewer": {"login": model.OWNER},
                "user": {"id": "U_fixture", "projectsV2": {"nodes": self.projects}},
            }
        if query == github.CREATE_PROJECT:
            self.project["title"] = variables["input"]["title"]
            self.projects.append(self.project)
            return {"createProjectV2": {"projectV2": self.project}}
        if query == github.UPDATE_PROJECT:
            self.project.update(variables["input"])
            return {"updateProjectV2": {"projectV2": self.project}}
        if query == github.STRUCTURE_QUERY:
            return {
                "node": {
                    "fields": {"nodes": list(self.fields.values())},
                    "views": {"nodes": self.views},
                }
            }
        if query == github.CREATE_FIELD:
            value = variables["input"]
            field = self.add_field(
                value["name"],
                value["dataType"],
                [option["name"] for option in value.get("singleSelectOptions", [])],
            )
            return {"createProjectV2Field": {"projectV2Field": field}}
        if query == github.ISSUE_QUERY:
            number = variables["number"]
            return {
                "repository": {
                    "issue": {
                        "id": f"I_fixture_{number}",
                        "url": (
                            "https://github.com/RoryGlenn/MasterAgent/issues/"
                            f"{number}"
                        ),
                        "title": f"Fixture issue {number}",
                    }
                }
            }
        if query == github.ITEMS_QUERY:
            start = int(variables["after"] or 0)
            end = start + self.page_size
            has_next = end < len(self.items)
            return {
                "node": {
                    "items": {
                        "nodes": self.items[start:end],
                        "pageInfo": {
                            "hasNextPage": has_next,
                            "endCursor": str(end) if has_next else None,
                        },
                    }
                }
            }
        if query == github.ADD_ITEM:
            number = int(variables["input"]["contentId"].removeprefix("I_fixture_"))
            item = self.add_item(number)
            return {"addProjectV2ItemById": {"item": {"id": item["id"]}}}
        if query == github.UPDATE_ITEM_FIELD:
            value = variables["input"]
            self.values[(value["itemId"], value["fieldId"])] = value["value"]
            field = next(
                field for field in self.fields.values()
                if field["id"] == value["fieldId"]
            )
            encoded = value["value"]
            if "singleSelectOptionId" in encoded:
                option = next(
                    option for option in field["options"]
                    if option["id"] == encoded["singleSelectOptionId"]
                )
                stored = {"name": option["name"], "optionId": option["id"]}
            else:
                stored = encoded
            item = next(
                item for item in self.items if item["id"] == value["itemId"]
            )
            item["fieldValues"]["nodes"] = [
                node for node in item["fieldValues"]["nodes"]
                if node["field"]["id"] != field["id"]
            ]
            item["fieldValues"]["nodes"].append({**stored, "field": field})
            return {
                "updateProjectV2ItemFieldValue": {
                    "projectV2Item": {"id": value["itemId"]}
                }
            }
        if query == github.CREATE_VIEW:
            view = {
                "id": f"PVTV_fixture_{len(self.views)}",
                "name": variables["input"]["name"],
            }
            self.views.append(view)
            return {"createProjectV2View": {"projectV2View": view}}
        if query == github.UPDATE_VIEW:
            value = variables["input"]
            view = next(view for view in self.views if view["id"] == value["viewId"])
            view.update(value)
            return {"updateProjectV2View": {"projectV2View": view}}
        raise AssertionError(f"Unexpected GraphQL operation {query!r}")

    def inputs_for(self, query: str) -> list[dict]:
        return [
            variables["input"] for operation, variables in self.operations
            if operation == query
        ]

    def run_main(self, args: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with (
            patch.object(github.shutil, "which", return_value="/fixture/bin/gh"),
            patch.object(github.subprocess, "run", side_effect=self.run),
            patch.object(github, "date") as fixture_date,
            contextlib.redirect_stdout(output),
        ):
            fixture_date.today.return_value = date(2026, 2, 3)
            result = bootstrap.main(args)
        return result, output.getvalue()


class BootstrapTests(unittest.TestCase):
    def test_new_project_seeds_exact_graphql_ids_and_typed_values(self):
        fixture = FixtureGitHub(existing=False)

        result, output = fixture.run_main([])

        self.assertEqual(result, 0)
        self.assertIn("[ok] WIP limit: 3/3", output)
        self.assertTrue(output.endswith(fixture.project["url"] + "\n"))
        self.assertEqual(len(fixture.inputs_for(github.CREATE_PROJECT)), 1)
        self.assertEqual(
            len(fixture.inputs_for(github.CREATE_FIELD)), len(model.FIELDS)
        )
        self.assertEqual(len(fixture.inputs_for(github.ADD_ITEM)), len(model.SEEDS))
        self.assertFalse(fixture.project["public"])
        self.assertEqual(
            {view["name"] for view in fixture.views},
            {view.name for view in model.VIEWS},
        )
        expected_values = {}
        for seed in model.SEEDS:
            values = {
                "Status": {"option": seed.status},
                "Outcome": {"text": seed.outcome},
                "Project": {"option": "MasterAgent"},
                "Stage": {"option": seed.stage},
                "Evidence level": {"option": seed.evidence},
                "Next validation": {"text": seed.validation},
                "User impact": {"option": "Expected"},
                "WIP owner": {"text": "Rory"},
                "Review date": {
                    "date": (
                        date(2026, 2, 3) + timedelta(days=seed.review_days)
                    ).isoformat()
                },
            }
            if seed.dependency:
                values["External dependency"] = {"text": seed.dependency}
            for name, value in values.items():
                field = fixture.fields[name]
                if "option" in value:
                    option = next(
                        option for option in field["options"]
                        if option["name"].casefold() == value["option"].casefold()
                    )
                    value = {"singleSelectOptionId": option["id"]}
                expected_values[(f"PVTI_fixture_{seed.number}", field["id"])] = value
        self.assertEqual(fixture.values, expected_values)
        for value in fixture.inputs_for(github.UPDATE_ITEM_FIELD):
            self.assertEqual(value["projectId"], fixture.project["id"])

    def test_existing_project_keeps_seed_metadata_until_explicit_refresh(self):
        fixture = FixtureGitHub(existing=False)
        fixture.run_main([])
        for name, value in (
            ("Outcome", {"text": "User-edited outcome"}),
            ("Review date", {"date": "2030-01-01"}),
            ("Status", {"singleSelectOptionId": "status_done"}),
        ):
            fixture.respond(github.UPDATE_ITEM_FIELD, {"input": {
                "itemId": "PVTI_fixture_171",
                "fieldId": fixture.fields[name]["id"],
                "value": value,
            }})
        original_items = copy.deepcopy(fixture.items)
        original_values = copy.deepcopy(fixture.values)
        fixture.operations.clear()

        result, output = fixture.run_main([])

        self.assertEqual(result, 0)
        self.assertIn("[ok] WIP limit: 2/3", output)
        self.assertEqual(fixture.items, original_items)
        self.assertEqual(fixture.values, original_values)
        self.assertEqual(fixture.inputs_for(github.ADD_ITEM), [])
        self.assertEqual(fixture.inputs_for(github.UPDATE_ITEM_FIELD), [])
        self.assertEqual(fixture.inputs_for(github.CREATE_PROJECT), [])
        self.assertIn("... on ProjectV2ItemFieldTextValue", github.ITEMS_QUERY)
        self.assertIn("... on ProjectV2ItemFieldDateValue", github.ITEMS_QUERY)

    def test_default_reconcile_fills_only_empty_seed_fields(self):
        fixture = FixtureGitHub()
        item = fixture.add_item(171, "In progress")
        for name, value in (
            ("Outcome", {"text": "User-edited outcome"}),
            ("Review date", {"date": "2030-01-01"}),
            ("Next validation", {"text": ""}),
        ):
            fixture.respond(github.UPDATE_ITEM_FIELD, {"input": {
                "itemId": item["id"],
                "fieldId": fixture.fields[name]["id"],
                "value": value,
            }})

        result, _ = fixture.run_main([])

        self.assertEqual(result, 0)
        self.assertEqual(len(fixture.inputs_for(github.ADD_ITEM)), 6)
        stored = github.item_values(item)
        self.assertEqual(stored["Outcome"], "User-edited outcome")
        self.assertEqual(stored["Review date"], "2030-01-01")
        self.assertEqual(stored["Status"], "In progress")
        self.assertEqual(stored["Next validation"], model.SEEDS[0].validation)
        preserved_ids = {
            fixture.fields[name]["id"]
            for name in ("Status", "Outcome", "Review date")
        }
        for update in fixture.inputs_for(github.UPDATE_ITEM_FIELD):
            if update["itemId"] == item["id"]:
                self.assertNotIn(update["fieldId"], preserved_ids)

    def test_no_seed_reconciles_structure_without_item_mutations(self):
        fixture = FixtureGitHub(existing=False)

        result, output = fixture.run_main(["--no-seed", "--refresh-seed"])

        self.assertEqual(result, 0)
        self.assertIn("[ok] WIP limit: 0/3", output)
        self.assertEqual(len(fixture.fields), len(model.FIELDS) + 2)
        self.assertEqual(len(fixture.views), len(model.VIEWS))
        self.assertEqual(fixture.items, [])
        self.assertEqual(fixture.inputs_for(github.ADD_ITEM), [])
        self.assertEqual(fixture.inputs_for(github.UPDATE_ITEM_FIELD), [])

    def test_custom_project_title_is_used_for_creation_and_audit(self):
        fixture = FixtureGitHub(existing=False)
        title = "Fixture planning board"

        result, _ = fixture.run_main(["--title", title, "--no-seed"])

        self.assertEqual(result, 0)
        self.assertEqual(fixture.project["title"], title)
        self.assertEqual(fixture.inputs_for(github.CREATE_PROJECT)[0]["title"], title)
        self.assertEqual(fixture.inputs_for(github.UPDATE_PROJECT)[0]["title"], title)
        fixture.operations.clear()

        result, output = fixture.run_main(["--title", title, "--audit-only"])

        self.assertEqual(result, 0)
        self.assertIn("[ok] WIP limit: 0/3", output)
        self.assertTrue(all(
            query.lstrip().startswith("query") for query, _ in fixture.operations
        ))

    def test_option_matching_normalizes_case_and_repeated_whitespace(self):
        fixture = FixtureGitHub()
        fixture.fields["Status"]["options"][1]["name"] = "  In   PROGRESS "
        for option in fixture.fields["Stage"]["options"]:
            if option["name"] == "Build":
                option["name"] = "  bUiLd "

        result, output = fixture.run_main(["--refresh-seed"])

        self.assertEqual(result, 0)
        self.assertIn("[ok] WIP limit: 3/3", output)
        self.assertEqual(
            fixture.values[("PVTI_fixture_171", fixture.fields["Status"]["id"])],
            {"singleSelectOptionId": "status_active"},
        )

    def test_existing_closed_project_stays_closed_during_reconciliation(self):
        fixture = FixtureGitHub()
        fixture.project["closed"] = True

        result, _ = fixture.run_main([])

        self.assertEqual(result, 0)
        self.assertTrue(fixture.project["closed"])
        updates = fixture.inputs_for(github.UPDATE_PROJECT)
        self.assertEqual(len(updates), 1)
        self.assertNotIn("closed", updates[0])

    def test_refresh_seed_reuses_existing_item_ids(self):
        fixture = FixtureGitHub()
        existing_ids = {fixture.add_item(seed.number)["id"] for seed in model.SEEDS}

        result, output = fixture.run_main(["--refresh-seed"])

        self.assertEqual(result, 0)
        self.assertIn("WIP limit: 3/3", output)
        self.assertEqual(fixture.inputs_for(github.ADD_ITEM), [])
        updates = fixture.inputs_for(github.UPDATE_ITEM_FIELD)
        self.assertEqual({update["itemId"] for update in updates}, existing_ids)
        self.assertEqual(len(updates), 67)

    def test_refresh_seed_adds_only_missing_issues(self):
        fixture = FixtureGitHub()
        fixture.add_item(model.SEEDS[0].number)

        result, _ = fixture.run_main(["--refresh-seed"])

        self.assertEqual(result, 0)
        added_ids = {
            value["contentId"] for value in fixture.inputs_for(github.ADD_ITEM)
        }
        self.assertEqual(
            added_ids, {f"I_fixture_{seed.number}" for seed in model.SEEDS[1:]}
        )
        self.assertEqual(len(fixture.items), len(model.SEEDS))


class AuditTests(unittest.TestCase):
    def assert_read_only(self, fixture):
        self.assertTrue(fixture.operations)
        self.assertTrue(all(
            query.lstrip().startswith("query") for query, _ in fixture.operations
        ))

    def test_audit_is_read_only_within_wip_limit(self):
        for active_count in (0, 1, 3):
            with self.subTest(active_count=active_count):
                fixture = FixtureGitHub()
                fixture.project.update(
                    public=True, closed=True, shortDescription="User description"
                )
                for number in range(active_count):
                    fixture.add_item(number, "In progress")
                fixture.add_item(100, "Todo")
                fixture.add_item(101, "Done")
                original = copy.deepcopy((
                    fixture.project, fixture.items, fixture.fields, fixture.views
                ))

                result, output = fixture.run_main(["--audit-only", "--refresh-seed"])

                self.assertEqual(result, 0)
                expected = f"[ok] WIP limit: {active_count}/3\n"
                expected += "".join(
                    f"  - Fixture issue {number}\n" for number in range(active_count)
                )
                expected += fixture.project["url"] + "\n"
                self.assertEqual(output, expected)
                self.assertEqual(
                    (fixture.project, fixture.items, fixture.fields, fixture.views),
                    original,
                )
                self.assert_read_only(fixture)

    def test_audit_missing_project_fails_without_mutations(self):
        fixture = FixtureGitHub(existing=False)

        with self.assertRaisesRegex(github.ProjectError, "was not found"):
            fixture.run_main(["--audit-only"])

        self.assertEqual(fixture.projects, [])
        self.assert_read_only(fixture)

    def test_audit_duplicate_project_names_fail_without_mutations(self):
        fixture = FixtureGitHub()
        fixture.projects.append({**fixture.project, "id": "PVT_duplicate", "number": 8})

        with self.assertRaisesRegex(github.ProjectError, "Multiple projects"):
            fixture.run_main(["--audit-only"])

        self.assert_read_only(fixture)

    def test_audit_counts_all_item_pages_and_fails_over_wip_limit(self):
        fixture = FixtureGitHub()
        fixture.page_size = 2
        for number in range(4):
            fixture.add_item(number, "In progress")

        with self.assertRaisesRegex(github.ProjectError, "WIP limit violated: 4"):
            fixture.run_main(["--audit-only"])

        cursors = [
            variables["after"] for query, variables in fixture.operations
            if query == github.ITEMS_QUERY
        ]
        self.assertEqual(cursors, [None, "2"])
        self.assert_read_only(fixture)

    def test_audit_reports_titles_of_active_pull_requests_and_drafts(self):
        fixture = FixtureGitHub()
        pull_request = fixture.add_item(1, "In progress")
        pull_request["content"] = {
            "title": "Fixture pull request",
            "url": "https://github.com/RoryGlenn/MasterAgent/pull/1",
        }
        draft = fixture.add_item(2, "In progress")
        draft["content"] = {"title": "Fixture draft"}

        result, output = fixture.run_main(["--audit-only"])

        self.assertEqual(result, 0)
        self.assertIn("  - Fixture pull request\n  - Fixture draft\n", output)
        self.assertTrue(output.endswith(fixture.project["url"] + "\n"))
        self.assert_read_only(fixture)

    def test_documented_script_audit_exit_status_and_read_only_commands(self):
        for scenario, expected_status, expected_message in (
            ("existing", 0, "[ok] WIP limit: 0/3"),
            ("missing", 2, "was not found"),
            ("over_limit", 2, "WIP limit violated: 4"),
        ):
            with (
                self.subTest(scenario=scenario),
                tempfile.TemporaryDirectory() as directory,
            ):
                fixture = FixtureGitHub(existing=scenario != "missing")
                if scenario == "over_limit":
                    for number in range(4):
                        fixture.add_item(number, "In progress")
                responses = {
                    github.ACCOUNT_QUERY: fixture.respond(github.ACCOUNT_QUERY, {}),
                    github.ITEMS_QUERY: fixture.respond(
                        github.ITEMS_QUERY, {"after": None}
                    ),
                }
                fixture_directory = Path(directory)
                response_path = fixture_directory / "responses.json"
                response_path.write_text(json.dumps(responses))
                calls_path = fixture_directory / "calls.jsonl"
                executable = fixture_directory / "gh"
                executable.write_text(f"#!{sys.executable}\n" + textwrap.dedent("""
                    import json
                    import os
                    from pathlib import Path
                    import sys

                    args = sys.argv[1:]
                    payload = None
                    if args == ["api", "graphql", "--input", "-"]:
                        payload = json.load(sys.stdin)
                    with Path(os.environ["FIXTURE_CALLS"]).open("a") as calls:
                        record = {"args": args, "payload": payload}
                        calls.write(json.dumps(record) + "\\n")
                    if args == ["auth", "status", "--hostname", "github.com"]:
                        raise SystemExit(0)
                    if (
                        payload is None
                        or not payload["query"].lstrip().startswith("query")
                    ):
                        print("Fixture rejected this command", file=sys.stderr)
                        raise SystemExit(99)
                    response_path = Path(os.environ["FIXTURE_RESPONSES"])
                    responses = json.loads(response_path.read_text())
                    print(json.dumps({"data": responses[payload["query"]]}))
                """))
                executable.chmod(0o700)
                process = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "tools/bootstrap_rory_operating_system.py",
                        "--audit-only",
                    ],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        "PATH": directory,
                        "FIXTURE_CALLS": str(calls_path),
                        "FIXTURE_RESPONSES": str(response_path),
                    },
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(process.returncode, expected_status, process.stderr)
                self.assertIn(expected_message, process.stdout + process.stderr)
                calls = [
                    json.loads(line) for line in calls_path.read_text().splitlines()
                ]
                self.assertEqual(
                    calls[0]["args"],
                    ["auth", "status", "--hostname", "github.com"],
                )
                for call in calls[1:]:
                    self.assertEqual(call["args"], ["api", "graphql", "--input", "-"])
                    self.assertTrue(
                        call["payload"]["query"].lstrip().startswith("query")
                    )


class SelfCheckTests(unittest.TestCase):
    def test_self_check_runs_before_github_cli_initialization(self):
        output = io.StringIO()
        with (
            patch.object(bootstrap, "Gh", side_effect=AssertionError("GitHub access")),
            contextlib.redirect_stdout(output),
        ):
            result = bootstrap.main(["--self-check"])

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue(),
            f"[ok] validated {len(github.GRAPHQL_DOCUMENTS)} GraphQL documents\n",
        )

    def test_invalid_static_documents_fail_before_github_access(self):
        for document in (
            "query { viewer { login }",
            "query { viewer(login: ] ) { login } }",
            'query { viewer(login: "unterminated) { login } }',
        ):
            with (
                self.subTest(document=document),
                patch.object(bootstrap, "GRAPHQL_DOCUMENTS", (document,)),
                patch.object(
                    bootstrap, "Gh", side_effect=AssertionError("GitHub access")
                ),
                self.assertRaises(bootstrap.BootstrapError),
            ):
                bootstrap.main([])

    def test_document_validation_ignores_strings_and_comments(self):
        document = (
            r'query { viewer(name: "braces \" } [") { login } # }' + "\n}"
        )
        with patch.object(bootstrap, "GRAPHQL_DOCUMENTS", (document,)):
            bootstrap.validate_graphql_documents()

    def test_documented_self_check_succeeds_without_github_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "tools/bootstrap_rory_operating_system.py",
                    "--self-check",
                ],
                cwd=ROOT,
                env={**os.environ, "PATH": directory},
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(
            f"[ok] validated {len(github.GRAPHQL_DOCUMENTS)} GraphQL documents",
            process.stdout,
        )


if __name__ == "__main__":
    unittest.main()
