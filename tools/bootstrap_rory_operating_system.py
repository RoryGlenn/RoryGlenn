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
    Gh,
    ProjectError,
    enforce_wip,
    ensure_fields,
    ensure_project,
    ensure_views,
    find_project,
    preflight,
    seed_issues,
)


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
        help="Read the existing project and check its three-item WIP limit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Create, seed, or audit the operating project."""

    args = parse_args(sys.argv[1:] if argv is None else argv)
    gh = Gh()
    preflight(gh, args.owner)
    if args.audit_only:
        project = find_project(gh, args.owner)
        count = enforce_wip(gh, project.id)
        print(f"[ok] WIP {count}/{MAX_WIP}")
        return 0

    project = ensure_project(gh, args.owner)
    fields = ensure_fields(gh, project.id)
    if project.created or args.refresh_seed:
        seed_issues(gh, project.id, fields)
    else:
        print("[skip] seed metadata already exists; use --refresh-seed to reapply it")
    ensure_views(gh, project.id, fields)
    count = enforce_wip(gh, project.id)
    print(f"[done] WIP {count}/{MAX_WIP}: {project.url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProjectError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        raise SystemExit(130)
