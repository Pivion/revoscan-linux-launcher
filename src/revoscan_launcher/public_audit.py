"""Reject common proprietary/user payloads from public AppImage staging trees."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_SUFFIXES = {".log", ".revox", ".ply", ".stl", ".obj", ".3mf", ".asc"}
FORBIDDEN_COMPONENTS = {"drive_c", "wineprefix", "projects"}


def audit_tree(root: Path) -> list[str]:
    root = Path(root)
    if not root.is_dir():
        return [f"Not a directory: {root}"]
    problems: list[str] = []
    for item in root.rglob("*"):
        relative = item.relative_to(root)
        parts = [part.casefold() for part in relative.parts]
        suffix = item.suffix.casefold()
        if suffix in FORBIDDEN_SUFFIXES:
            problems.append(f"Forbidden user-data file ({suffix}): {relative}")
        if any(part in FORBIDDEN_COMPONENTS for part in parts):
            problems.append(f"Forbidden prefix/project path component: {relative}")
        if "program files" in parts and "revo scan 6" in parts:
            problems.append(f"Proprietary Revo Scan installation path: {relative}")
        if item.is_file() and item.name.casefold().startswith("revoscan6-") and suffix == ".exe":
            problems.append(f"Vendor installer present: {relative}")
    return sorted(set(problems))
