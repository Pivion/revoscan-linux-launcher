"""Construct the isolated Wine/Vulkan environment used by the GUI launcher."""

from __future__ import annotations

import os
from pathlib import Path

from .gpu import GpuAdapter, GpuTarget, build_mapping_environment

LAYER_NAME = "VK_LAYER_REVOSCAN_LINUX_GPU_MAP"


def build_revoscan_environment(
    appdir: Path,
    prefix: Path,
    adapter: GpuAdapter | None,
    target: GpuTarget | None,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    appdir = Path(appdir)
    prefix = Path(prefix)
    wine_candidates = (
        appdir / "opt/wine-staging/lib/wine",
        appdir / "usr/lib64/wine-wow64/wine",
        appdir / "usr/lib/wine",
    )
    wine_lib = next((candidate for candidate in wine_candidates if candidate.exists()), wine_candidates[-1])
    layer_dir = appdir / "usr/share/vulkan/explicit_layer.d"

    env["WINEPREFIX"] = str(prefix)
    env["WINEARCH"] = "win64"
    env["WINELOADER"] = str(appdir / "usr/bin/wine64")
    env["WINESERVER"] = str(appdir / "usr/bin/wineserver64")
    dll_paths = [wine_lib]
    for name in ("x86_64-unix", "x86_64-windows", "i386-unix", "i386-windows"):
        candidate = wine_lib / name
        if candidate.is_dir():
            dll_paths.append(candidate)
    env["WINEDLLPATH"] = ":".join(str(path) for path in dll_paths)
    host_library_path = env.pop("REVOSCAN_HOST_LD_LIBRARY_PATH", None)
    if host_library_path is None:
        host_library_path = env.get("LD_LIBRARY_PATH", "")
    library_paths = [str(layer_dir), str(wine_lib / "x86_64-unix"), str(wine_lib.parent)]
    if host_library_path:
        library_paths.append(host_library_path)
    env["LD_LIBRARY_PATH"] = ":".join(library_paths)

    # Do not inherit a stale copy of this layer or stale mapping values.
    for key in tuple(env):
        if key.startswith("REVOSCAN_MAP_"):
            env.pop(key, None)
    active_layers = [item for item in env.get("VK_INSTANCE_LAYERS", "").split(":") if item and item != LAYER_NAME]
    if adapter is not None and target is not None:
        env.update(build_mapping_environment(adapter, target))
        active_layers.append(LAYER_NAME)
        env["VK_LAYER_PATH"] = str(layer_dir)
    elif env.get("VK_LAYER_PATH") == str(layer_dir):
        env.pop("VK_LAYER_PATH", None)
    if active_layers:
        env["VK_INSTANCE_LAYERS"] = ":".join(active_layers)
    else:
        env.pop("VK_INSTANCE_LAYERS", None)
    env.setdefault("WINEDEBUG", "-all")
    return env


def installed_executable(prefix: Path) -> Path:
    return Path(prefix) / "drive_c/Program Files/Revo Scan 6/RevoScan6.exe"
