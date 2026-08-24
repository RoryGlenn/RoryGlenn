#!/usr/bin/env python3
"""Install Rory's reusable Codex skills, agents, guidance, and lane helper."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final, Sequence

SCHEMA: Final = "rory-codex-engineering-system/v1"
GUIDANCE_START: Final = "<!-- RORY_CODEX_ENGINEERING_SYSTEM:START -->"
GUIDANCE_END: Final = "<!-- RORY_CODEX_ENGINEERING_SYSTEM:END -->"
CONFIG_COMMENT: Final = "# RORY_CODEX_ENGINEERING_SYSTEM"
CONFIG_START: Final = "# RORY_CODEX_ENGINEERING_SYSTEM:START"
CONFIG_END: Final = "# RORY_CODEX_ENGINEERING_SYSTEM:END"
CONFIG_VALUES: Final[dict[str, str]] = {
    "enabled": "true",
    "max_concurrent_threads_per_session": "3",
    "interrupt_message": "true",
}


class InstallError(RuntimeError):
    """Safe operator-facing installation failure."""


def repository_root() -> Path:
    """Return the source repository root."""
    return Path(__file__).resolve().parent.parent


def sha256_bytes(value: bytes) -> str:
    """Return a SHA-256 hex digest."""
    return hashlib.sha256(value).hexdigest()


def digest_path(path: Path) -> str:
    """Hash one file or directory deterministically."""
    if path.is_symlink():
        return f"symlink:{path.resolve()}"
    if path.is_file():
        return sha256_bytes(path.read_bytes())
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
    raise InstallError(f"Cannot hash missing or unsupported path: {path}")


def atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    """Write a UTF-8 file atomically with private default permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def backup(path: Path, *, dry_run: bool) -> str | None:
    """Create a private timestamped backup and return its path."""
    if not path.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = (
        path.parent
        / "backups"
        / f"{path.name}.{timestamp}.{sha256_bytes(str(path).encode())[:8]}.bak"
    )
    if dry_run:
        print(f"[dry-run] backup {path} -> {destination}")
        return str(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    os.chmod(destination, 0o600)
    return str(destination)


def parse_skill_frontmatter(path: Path) -> dict[str, str]:
    """Parse the required simple YAML frontmatter from one skill."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InstallError(f"Skill has no frontmatter: {path}")
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as exc:
        raise InstallError(f"Skill frontmatter is not closed: {path}") from exc
    values: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if not separator:
            raise InstallError(f"Unsupported skill frontmatter line in {path}: {line!r}")
        values[key.strip()] = value.strip()
    for required in ("name", "description"):
        if not values.get(required):
            raise InstallError(f"Skill {path} is missing {required!r}.")
    return values


def source_inventory(root: Path) -> tuple[list[Path], list[Path], Path, Path, Path]:
    """Resolve and validate all installable source paths."""
    skills_root = root / ".agents" / "skills"
    agents_root = root / ".codex" / "agents"
    guidance = root / "codex" / "global-AGENTS.md"
    config = root / ".codex" / "config.toml.example"
    lane_tool = root / "tools" / "codex_lanes.py"

    skills = sorted(path.parent for path in skills_root.glob("*/SKILL.md"))
    agents = sorted(agents_root.glob("*.toml"))
    if len(skills) != 4:
        raise InstallError(f"Expected 4 skills, found {len(skills)}.")
    if len(agents) != 3:
        raise InstallError(f"Expected 3 custom agents, found {len(agents)}.")
    if not all(path.is_file() for path in (guidance, config, lane_tool)):
        raise InstallError("One or more required Codex system source files are missing.")
    return skills, agents, guidance, config, lane_tool


def self_check(root: Path) -> None:
    """Validate the checked-in engineering system without mutating the home directory."""
    skills, agents, guidance, config, lane_tool = source_inventory(root)

    names: set[str] = set()
    for skill in skills:
        metadata = parse_skill_frontmatter(skill / "SKILL.md")
        name = metadata["name"]
        if name != skill.name:
            raise InstallError(
                f"Skill directory {skill.name!r} does not match name {name!r}."
            )
        if name in names:
            raise InstallError(f"Duplicate skill name: {name}")
        names.add(name)

    agent_names: set[str] = set()
    for agent in agents:
        with agent.open("rb") as handle:
            value = tomllib.load(handle)
        for required in ("name", "description", "developer_instructions"):
            if not isinstance(value.get(required), str) or not value[required].strip():
                raise InstallError(f"Agent {agent} is missing {required!r}.")
        name = str(value["name"])
        if name in agent_names:
            raise InstallError(f"Duplicate custom agent name: {name}")
        agent_names.add(name)
        if value.get("sandbox_mode") not in {"read-only", "workspace-write"}:
            raise InstallError(f"Agent {agent} has an unsupported sandbox_mode.")

    text = guidance.read_text(encoding="utf-8")
    if text.count(GUIDANCE_START) != 1 or text.count(GUIDANCE_END) != 1:
        raise InstallError("Global guidance must contain exactly one managed block.")

    with config.open("rb") as handle:
        parsed = tomllib.load(handle)
    agents_table = parsed.get("agents")
    if not isinstance(agents_table, dict):
        raise InstallError("Config example has no [agents] table.")
    if agents_table.get("max_concurrent_threads_per_session") != 3:
        raise InstallError("Config example does not enforce the three-thread limit.")

    if not os.access(lane_tool, os.R_OK):
        raise InstallError("Lane helper is unreadable.")
    print(
        f"[ok] {len(skills)} skills, {len(agents)} custom agents, "
        "global guidance, config, and lane helper"
    )


def load_manifest(path: Path) -> dict[str, Any]:
    """Load an optional installation manifest."""
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"Installation manifest is malformed: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise InstallError(f"Unsupported installation manifest: {path}")
    return value


def copy_managed(
    source: Path,
    target: Path,
    *,
    prior: dict[str, Any] | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Install one managed file or directory by copy."""
    if target.exists() or target.is_symlink():
        if not prior or prior.get("mode") != "copy":
            raise InstallError(f"Refusing to replace unmanaged path: {target}")
        expected = prior.get("digest")
        if expected != digest_path(target):
            raise InstallError(f"Managed copy was modified; refusing to overwrite: {target}")
        if dry_run:
            print(f"[dry-run] replace managed copy {target}")
        elif target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    if dry_run:
        print(f"[dry-run] copy {source} -> {target}")
        installed_digest = digest_path(source)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
            if os.access(source, os.X_OK):
                target.chmod(target.stat().st_mode | 0o100)
        installed_digest = digest_path(target)
    return {
        "source": str(source),
        "target": str(target),
        "mode": "copy",
        "digest": installed_digest,
    }


def symlink_managed(
    source: Path,
    target: Path,
    *,
    prior: dict[str, Any] | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Install one managed file or directory by symbolic link."""
    if target.exists() or target.is_symlink():
        if target.is_symlink() and target.resolve() == source.resolve():
            print(f"[reuse] {target}")
            return {
                "source": str(source),
                "target": str(target),
                "mode": "symlink",
                "digest": f"symlink:{source.resolve()}",
            }
        if not prior:
            raise InstallError(f"Refusing to replace unmanaged path: {target}")
        raise InstallError(f"Managed target no longer points to its source: {target}")

    if dry_run:
        print(f"[dry-run] symlink {target} -> {source}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=source.is_dir())
    return {
        "source": str(source),
        "target": str(target),
        "mode": "symlink",
        "digest": f"symlink:{source.resolve()}",
    }


def install_path(
    source: Path,
    target: Path,
    *,
    mode: str,
    prior: dict[str, Any] | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Install one managed source path."""
    if mode == "symlink":
        return symlink_managed(source, target, prior=prior, dry_run=dry_run)
    return copy_managed(source, target, prior=prior, dry_run=dry_run)


def upsert_guidance(target: Path, source: Path, *, dry_run: bool) -> dict[str, Any]:
    """Insert or replace the managed global AGENTS.md block."""
    block = source.read_text(encoding="utf-8").strip()
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    start_count = current.count(GUIDANCE_START)
    end_count = current.count(GUIDANCE_END)
    if start_count != end_count or start_count > 1:
        raise InstallError(f"Global guidance markers are malformed in {target}.")

    if start_count == 1:
        pattern = re.compile(
            re.escape(GUIDANCE_START) + r".*?" + re.escape(GUIDANCE_END),
            re.DOTALL,
        )
        updated = pattern.sub(block, current).rstrip() + "\n"
    else:
        prefix = current.rstrip()
        updated = f"{prefix}\n\n{block}\n" if prefix else f"{block}\n"

    if updated == current:
        print(f"[reuse] global guidance {target}")
        backup_path = None
    else:
        backup_path = backup(target, dry_run=dry_run)
        if dry_run:
            print(f"[dry-run] update global guidance {target}")
        else:
            atomic_write(target, updated)
    return {
        "path": str(target),
        "digest": sha256_bytes(updated.encode("utf-8")),
        "backup": backup_path,
    }


def table_bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    """Locate one exact TOML table."""
    header = f"[{name}]"
    indexes = [index for index, line in enumerate(lines) if line.strip() == header]
    if len(indexes) > 1:
        raise InstallError(f"Config contains multiple {header} tables.")
    if not indexes:
        return None
    start = indexes[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    return start, end


def merge_config(
    target: Path,
    *,
    dry_run: bool,
    prior: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the bounded [agents] settings into config.toml."""
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    if current.strip():
        try:
            tomllib.loads(current)
        except tomllib.TOMLDecodeError as exc:
            raise InstallError(f"Existing Codex config is invalid: {target}: {exc}") from exc

    lines = current.splitlines()
    bounds = table_bounds(lines, "agents")
    previous: dict[str, str | None] = {}
    added_section = bounds is None

    if bounds is None:
        if any(re.match(r"^\s*agents\.", line) for line in lines):
            raise InstallError(
                "Config uses dotted agents.* keys; merge the provided "
                ".codex/config.toml.example manually."
            )
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(
            [
                CONFIG_START,
                "[agents]",
                *(
                    f"{key} = {value}  {CONFIG_COMMENT}"
                    for key, value in CONFIG_VALUES.items()
                ),
                CONFIG_END,
            ]
        )
    else:
        start, end = bounds
        for key, value in CONFIG_VALUES.items():
            matches = [
                index
                for index in range(start + 1, end)
                if re.match(rf"^\s*{re.escape(key)}\s*=", lines[index])
            ]
            if len(matches) > 1:
                raise InstallError(f"Config contains duplicate agents.{key} values.")
            replacement = f"{key} = {value}  {CONFIG_COMMENT}"
            if matches:
                index = matches[0]
                previous[key] = lines[index]
                lines[index] = replacement
            else:
                previous[key] = None
                lines.insert(end, replacement)
                end += 1

    updated = "\n".join(lines).rstrip() + "\n"
    try:
        tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"Merged Codex config would be invalid: {exc}") from exc

    if prior and str(prior.get("path")) == str(target):
        backup_path = prior.get("backup")
        recovery_added_section = bool(prior.get("added_section"))
        recovery_previous = prior.get("previous", {})
    else:
        backup_path = backup(target, dry_run=dry_run)
        recovery_added_section = added_section
        recovery_previous = previous

    if dry_run:
        print(f"[dry-run] merge agent settings into {target}")
    else:
        atomic_write(target, updated)
    return {
        "path": str(target),
        "digest": sha256_bytes(updated.encode("utf-8")),
        "backup": backup_path,
        "added_section": recovery_added_section,
        "previous": recovery_previous,
    }


def remove_guidance(target: Path, *, dry_run: bool) -> None:
    """Remove the managed guidance block while preserving unrelated text."""
    if not target.exists():
        return
    current = target.read_text(encoding="utf-8")
    if current.count(GUIDANCE_START) != 1 or current.count(GUIDANCE_END) != 1:
        print(f"[keep] guidance markers changed; not modifying {target}")
        return
    pattern = re.compile(
        r"\n*" + re.escape(GUIDANCE_START) + r".*?" + re.escape(GUIDANCE_END) + r"\n*",
        re.DOTALL,
    )
    updated = pattern.sub("\n", current).strip()
    if dry_run:
        print(f"[dry-run] remove managed guidance from {target}")
    elif updated:
        atomic_write(target, updated + "\n")
    else:
        target.unlink()


def restore_config(record: dict[str, Any], *, dry_run: bool) -> None:
    """Remove or restore managed [agents] keys without touching other config."""
    target = Path(str(record.get("path", ""))).expanduser()
    if not target.exists():
        return
    current = target.read_text(encoding="utf-8")
    lines = current.splitlines()

    if record.get("added_section"):
        start_indexes = [i for i, line in enumerate(lines) if line.strip() == CONFIG_START]
        end_indexes = [i for i, line in enumerate(lines) if line.strip() == CONFIG_END]
        if len(start_indexes) != 1 or len(end_indexes) != 1:
            print(f"[keep] managed config markers changed; not modifying {target}")
            return
        start, end = start_indexes[0], end_indexes[0]
        if start > end:
            print(f"[keep] managed config markers are reversed; not modifying {target}")
            return
        del lines[start : end + 1]
    else:
        previous = record.get("previous")
        if not isinstance(previous, dict):
            print(f"[keep] config recovery metadata missing; not modifying {target}")
            return
        bounds = table_bounds(lines, "agents")
        if bounds is None:
            print(f"[keep] [agents] table was removed; not modifying {target}")
            return
        start, end = bounds
        for key, old_line in previous.items():
            matches = [
                index
                for index in range(start + 1, end)
                if re.match(rf"^\s*{re.escape(str(key))}\s*=", lines[index])
                and CONFIG_COMMENT in lines[index]
            ]
            if len(matches) != 1:
                print(f"[keep] managed agents.{key} changed; not modifying that key")
                continue
            index = matches[0]
            if old_line is None:
                del lines[index]
                end -= 1
            else:
                lines[index] = str(old_line)

    updated = "\n".join(lines).rstrip()
    if updated:
        updated += "\n"
        try:
            tomllib.loads(updated)
        except tomllib.TOMLDecodeError as exc:
            raise InstallError(f"Uninstall would make config invalid: {exc}") from exc
    if dry_run:
        print(f"[dry-run] restore {target}")
    elif updated:
        atomic_write(target, updated)
    else:
        target.unlink()


def uninstall(home: Path, manifest_path: Path, *, dry_run: bool) -> None:
    """Remove only artifacts still owned by this installer."""
    manifest = load_manifest(manifest_path)
    entries = manifest.get("entries")
    if isinstance(entries, list):
        for entry in reversed(entries):
            if not isinstance(entry, dict):
                continue
            target = Path(str(entry.get("target", ""))).expanduser()
            mode = entry.get("mode")
            if not (target.exists() or target.is_symlink()):
                continue
            if mode == "symlink":
                source = Path(str(entry.get("source", ""))).expanduser()
                if target.is_symlink() and target.resolve() == source.resolve():
                    if dry_run:
                        print(f"[dry-run] remove symlink {target}")
                    else:
                        target.unlink()
                else:
                    print(f"[keep] modified or replaced target: {target}")
            elif mode == "copy":
                if digest_path(target) == entry.get("digest"):
                    if dry_run:
                        print(f"[dry-run] remove managed copy {target}")
                    elif target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                else:
                    print(f"[keep] modified managed copy: {target}")

    guidance = manifest.get("guidance")
    if isinstance(guidance, dict):
        remove_guidance(Path(str(guidance.get("path", ""))), dry_run=dry_run)
    config = manifest.get("config")
    if isinstance(config, dict):
        restore_config(config, dry_run=dry_run)

    if dry_run:
        print(f"[dry-run] remove manifest {manifest_path}")
    else:
        if manifest_path.exists():
            manifest_path.unlink()
        state_dir = manifest_path.parent
        try:
            state_dir.rmdir()
        except OSError:
            pass
    print("[done] Codex engineering system uninstalled.")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Install reusable Codex skills, custom agents, guidance, and "
            "worktree tooling."
        )
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--copy", action="store_true", help="Copy instead of symlinking.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Install, validate, or uninstall the system."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = repository_root()
    self_check(root)
    if args.self_check:
        return 0

    home = args.home.expanduser().resolve()
    state_dir = home / ".codex" / "rory-engineering-system"
    manifest_path = state_dir / "manifest.json"
    if args.uninstall:
        uninstall(home, manifest_path, dry_run=args.dry_run)
        return 0

    prior_manifest = load_manifest(manifest_path)
    prior_entries = {
        str(entry.get("target")): entry
        for entry in prior_manifest.get("entries", [])
        if isinstance(entry, dict)
    }

    skills, agents, guidance_source, _, lane_tool = source_inventory(root)
    install_mode = "copy" if args.copy or os.name == "nt" else "symlink"
    entries: list[dict[str, Any]] = []

    for source in skills:
        target = home / ".agents" / "skills" / source.name
        entries.append(
            install_path(
                source,
                target,
                mode=install_mode,
                prior=prior_entries.get(str(target)),
                dry_run=args.dry_run,
            )
        )

    for source in agents:
        target = home / ".codex" / "agents" / source.name
        entries.append(
            install_path(
                source,
                target,
                mode=install_mode,
                prior=prior_entries.get(str(target)),
                dry_run=args.dry_run,
            )
        )

    binary_target = home / ".local" / "bin" / "codex-lanes"
    entries.append(
        install_path(
            lane_tool,
            binary_target,
            mode=install_mode,
            prior=prior_entries.get(str(binary_target)),
            dry_run=args.dry_run,
        )
    )

    guidance_target = home / ".codex" / "AGENTS.md"
    guidance = upsert_guidance(
        guidance_target,
        guidance_source,
        dry_run=args.dry_run,
    )
    config = merge_config(
        home / ".codex" / "config.toml",
        dry_run=args.dry_run,
        prior=(
            prior_manifest.get("config")
            if isinstance(prior_manifest.get("config"), dict)
            else None
        ),
    )

    manifest = {
        "schema": SCHEMA,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root),
        "install_mode": install_mode,
        "entries": entries,
        "guidance": guidance,
        "config": config,
    }
    if args.dry_run:
        print(f"[dry-run] write manifest {manifest_path}")
    else:
        state_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(manifest_path, json.dumps(manifest, indent=2) + "\n")
        os.chmod(manifest_path, 0o600)

    override = home / ".codex" / "AGENTS.override.md"
    if override.exists() and override.read_text(encoding="utf-8").strip():
        print(
            f"[warning] {override} takes precedence over ~/.codex/AGENTS.md. "
            "Merge the Rory workflow block into the override or remove the override."
        )

    print(f"[done] installed {len(skills)} skills and {len(agents)} custom agents")
    print("[done] configured at most 3 concurrent subagent threads")
    print(f"[done] lane helper: {binary_target}")
    print("Restart Codex, then use /skills or type $ to select a workflow.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except KeyboardInterrupt:
        raise SystemExit(130)
