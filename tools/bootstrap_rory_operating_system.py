#!/usr/bin/env python3
"""Create or audit Rory's private cross-repository GitHub Projects board.

Requirements
------------
- GitHub CLI (``gh``)
- authentication as ``RoryGlenn``
- a token with the ``project`` scope, or ``read:project`` for audits
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from rory_operating_system_data import MAX_WIP, OWNER, TITLE
from rory_operating_system_github import (
    GRAPHQL_DOCUMENTS,
    Gh,
    ProjectError,
    audit_wip,
    ensure_fields,
    ensure_project,
    ensure_views,
    find_project,
    preflight,
    seed_issues,
)

BootstrapError = ProjectError


def validate_graphql_documents() -> None:
    """Catch truncated static GraphQL before any GitHub operation."""

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
                    raise BootstrapError(
                        f"GraphQL document {index} has mismatched delimiters."
                    )
        if in_string or stack:
            raise BootstrapError(
                f"GraphQL document {index} is truncated or unbalanced."
            )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=f"Create or reconcile {TITLE!r}.")
    parser.add_argument("--owner", default=OWNER)
    parser.add_argument("--title", default=TITLE)
    parser.add_argument(
        "--refresh-seed",
        action="store_true",
        help="Reapply the initial metadata to seeded issues in an existing project.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Reconcile the project structure without adding or updating seeds.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Read the existing project and check its three-item WIP limit.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Validate static GraphQL without contacting GitHub.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Create, seed, or audit the operating project."""

    args = parse_args(sys.argv[1:] if argv is None else argv)
    validate_graphql_documents()
    if args.self_check:
        print(f"[ok] validated {len(GRAPHQL_DOCUMENTS)} GraphQL documents")
        return 0

    gh = Gh()
    preflight(gh, args.owner)
    if args.audit_only:
        project = find_project(gh, args.owner, args.title)
    else:
        project = ensure_project(gh, args.owner, args.title)
        fields = ensure_fields(gh, project.id)
        if not args.no_seed:
            seed_issues(gh, project.id, fields, args.refresh_seed)
        ensure_views(gh, project.id, fields)
    active = audit_wip(gh, project.id)
    print(f"[ok] WIP limit: {len(active)}/{MAX_WIP}")
    for title in active:
        print(f"  - {title}")
    print(project.url)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        raise SystemExit(130)
