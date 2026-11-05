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


def check_vulkan_identity(output: TextIO) -> int:
    """Report the GPU identity Vulkan consumers see, with mapping applied.

    Runs the host ``vulkaninfo --summary`` with the same mapping environment
    the launcher builds, so the user can verify what an app would read.
    """
    import shutil

    vulkaninfo = shutil.which("vulkaninfo")
    if not vulkaninfo:
        print(
            "vulkaninfo is not installed (install the vulkan-tools package); "
            "cannot run the Vulkan identity check.",
            file=output,
        )
        return 2
    from revoscan_launcher.gpu import AMD_TARGETS, build_mapping_environment, detect_adapters

    try:
        adapters = detect_adapters()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"GPU detection failed: {exc}", file=output)
        return 1
    source = next((a for a in adapters if a.vendor in {"amd", "intel"}), None)
    if source is None:
        print("No AMD or Intel adapter detected; nothing to map.", file=output)
        return 0
    target = AMD_TARGETS["intel-b580"]
    mapping_env = build_mapping_environment(source, target)
    mapping_env["VK_INSTANCE_LAYERS"] = "VK_LAYER_REVOSCAN_LINUX_GPU_MAP"
    appdir = os.environ.get("APPDIR")
    if appdir:
        # Inside the AppImage the layer manifest lives in the bundled layer
        # dir; an ambient VK_LAYER_PATH could otherwise shadow it.
        mapping_env["VK_LAYER_PATH"] = str(Path(appdir) / "usr/share/vulkan/explicit_layer.d")
    print(
        f"Mapping profile: {source.identity} ({source.name}) -> {target.name}",
        file=output,
    )
    run_env = {**os.environ, **mapping_env}
    if not appdir:
        # Outside the AppImage, an ambient VK_LAYER_PATH (often a stale path
        # from other tooling) shadows the default layer search paths and
        # silently hides the layer. Drop it so defaults are scanned.
        run_env.pop("VK_LAYER_PATH", None)
    try:
        completed = subprocess.run(
            ["vulkaninfo", "--summary"],
            env=run_env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"vulkaninfo run failed: {exc}", file=output)
        return 1
    summary = completed.stdout
    for line in summary.splitlines():
        if "vendorID" in line or "deviceID" in line or "deviceName" in line:
            print(line.strip(), file=output)
    applied = any(
        f"0x{target.vendor_id:04x}" in line and "vendorID" in line
        for line in summary.splitlines()
    )
    print(f"Mapping target requested: {target.name}", file=output)
    if applied:
        print("Mapping applied: the reported identity is the mapped target.", file=output)
    else:
        print(
            "WARNING: mapping did not apply. Check that the Vulkan layer manifest is "
            "discoverable (VK_LAYER_PATH) and that VK_INSTANCE_LAYERS names the layer.",
            file=output,
        )
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
    if args == ["--vulkan-check"]:
        return check_vulkan_identity(output)
    if main_function is None:
        from revoscan_launcher.gui import main as main_function
    main_function()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
