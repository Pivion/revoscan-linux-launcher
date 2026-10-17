#!/usr/bin/env python3
"""Audit an AppDir or type-2 AppImage before public release."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from revoscan_launcher.public_audit import audit_tree  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} APPDIR_OR_APPIMAGE", file=sys.stderr)
        return 2
    target = Path(argv[1]).expanduser().resolve()
    if target.is_dir():
        root = target
        return _report(root)
    if not target.is_file() or not os.access(target, os.X_OK):
        print(f"Not an executable AppImage: {target}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="revoscan-audit-") as temp:
        env = os.environ.copy()
        env["APPIMAGE_EXTRACT_AND_RUN"] = "1"
        result = subprocess.run(
            [str(target), "--appimage-extract"],
            cwd=temp,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        extracted = Path(temp) / "squashfs-root"
        if result.returncode != 0 or not extracted.is_dir():
            print("Could not safely extract AppImage for audit:", file=sys.stderr)
            print(result.stdout[-4000:], file=sys.stderr)
            return 2
        return _report(extracted)


def _report(root: Path) -> int:
    problems = audit_tree(root)
    if problems:
        print("PUBLIC ARTIFACT AUDIT FAILED:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"Public artifact audit passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
