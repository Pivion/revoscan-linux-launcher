"""Stable executable entrypoint for PyInstaller and AppRun."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import TextIO


def check_bundled_wine(output: TextIO) -> int:
    appdir_value = os.environ.get("APPDIR")
    if not appdir_value:
        print("APPDIR is not set; this check must run from the AppImage.", file=output)
        return 2
    appdir = Path(appdir_value)
    wine = appdir / "usr/bin/wine64"
    if not wine.is_file():
        print(f"Bundled Wine executable is missing: {wine}", file=output)
        return 2
    from revoscan_launcher.runtime import build_revoscan_environment

    try:
        with tempfile.TemporaryDirectory(prefix="revoscan-wine-check-") as prefix:
            env = build_revoscan_environment(appdir, Path(prefix), None, None)
            env["WINELOADER"] = str(wine)
            completed = subprocess.run(
                [str(wine), "--version"],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Bundled Wine check failed: {exc}", file=output)
        return 1
    report = (completed.stdout + completed.stderr).strip()
    print(report or f"Bundled Wine exited with {completed.returncode} and no output.", file=output)
    return completed.returncode


def run(
    main_function: Callable[[], None] | None = None,
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    output = sys.stdout if stdout is None else stdout
    if args == ["--check-latest-installer"]:
        from revoscan_launcher.installer import fetch_latest_official_installer

        release = fetch_latest_official_installer()
        print(f"{release.version} {release.url}", file=output)
        return 0
    if args == ["--check-wine"]:
        return check_bundled_wine(output)
    if main_function is None:
        from revoscan_launcher.gui import main as main_function
    main_function()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
