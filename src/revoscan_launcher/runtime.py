"""Construct the isolated Wine/Vulkan environment used by the GUI launcher."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from .gpu import GpuAdapter, GpuTarget, build_mapping_environment

LAYER_NAME = "VK_LAYER_REVOSCAN_LINUX_GPU_MAP"
LAYER_LIBRARY = "librevoscan_gpu_map.so"


def mapping_layer_dir(appdir: Path) -> Path | None:
    """Directory holding a usable layer manifest + shared object, else None.

    A VK_LAYER_PATH pointing at a directory without the layer makes the Vulkan
    loader search only that path, so mapping silently never applies. Callers
    must check this before claiming a mapping is active.
    """
    layer_dir = Path(appdir) / "usr/share/vulkan/explicit_layer.d"
    manifest = layer_dir / f"{LAYER_NAME}.json"
    library = layer_dir / LAYER_LIBRARY
    if manifest.is_file() and library.is_file():
        return layer_dir
    return None



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
    library_paths = []
    if layer_dir.is_dir():
        library_paths.append(str(layer_dir))
    library_paths += [str(wine_lib / "x86_64-unix"), str(wine_lib.parent)]

    if host_library_path:
        library_paths.append(host_library_path)
    env["LD_LIBRARY_PATH"] = ":".join(library_paths)

    # Do not inherit a stale copy of this layer or stale mapping values.
    for key in tuple(env):
        if key.startswith("REVOSCAN_MAP_"):
            env.pop(key, None)
    active_layers = [item for item in env.get("VK_INSTANCE_LAYERS", "").split(":") if item and item != LAYER_NAME]
    usable_layer_dir = (
        mapping_layer_dir(appdir) if (adapter is not None and target is not None) else None
    )
    if usable_layer_dir is not None and adapter is not None and target is not None:
        env.update(build_mapping_environment(adapter, target))
        active_layers.append(LAYER_NAME)
        env["VK_LAYER_PATH"] = str(usable_layer_dir)
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


_D3D_KEY = "HKCU\\Software\\Wine\\Direct3D"


def _wine_reg(wine: Path, env: dict[str, str], args: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [str(wine), "reg", *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    ok = completed.returncode == 0
    return ok, (completed.stdout + completed.stderr).strip()


def set_wine_gpu_override(prefix: Path, wine: Path, env: dict[str, str], target) -> list[str]:
    """Make Wine's DXGI/wined3d report the mapped adapter.

    Revo Scan's GPU check (RvGPUUtils::getDiscreteGpuInfo, "Vulkan
    EnumerateVulkanDevices") actually enumerates DXGI adapters. Wine's default
    GL-backed wined3d synthesises its own identity ("Intel(R) HD Graphics
    4000", PCI 8086:0162, 1.5 GiB) and ignores the VideoPci* registry values,
    so the layer cannot influence it. Selecting wined3d's Vulkan renderer makes
    DXGI read the Vulkan physical-device properties instead — the values the
    mapping layer already rewrites.
    """
    report: list[str] = []
    ok, message = _wine_reg(
        wine, env,
        ["add", _D3D_KEY, "/v", "renderer", "/t", "REG_SZ", "/d", "vulkan", "/f"],
    )
    report.append(f"renderer=vulkan: {'ok' if ok else 'FAILED ' + message}")
    if not ok:
        return report
    # Confirm the identity DXGI will report, from inside the prefix.
    ok, message = _wine_reg(
        wine, env,
        ["query", _D3D_KEY, "/v", "renderer"],
    )
    report.append(f"renderer: {message.splitlines()[-1].strip() if message else 'unknown'}")
    return report


def clear_wine_gpu_override(prefix: Path, wine: Path, env: dict[str, str]) -> list[str]:
    report: list[str] = []
    # Drop the Vulkan-renderer selection plus any legacy identity values that a
    # previous launcher version wrote and this Wine build ignores.
    for value in ("renderer", "VideoPciVendorID", "VideoPciDeviceID", "VideoDescription"):
        ok, message = _wine_reg(wine, env, ["delete", _D3D_KEY, "/v", value, "/f"])
        report.append(f"{value}: {'cleared' if ok else message or 'absent'}")
    return report


def sanitize_bluetooth(prefix: Path) -> list[str]:
    """Remove Wine's Bluetooth radio from a prefix so Revo Scan can start.

    Revo Scan's simpleble.dll calls WinRT Bluetooth APIs
    (BluetoothAdapter::FromIdAsync, DeviceInformation::CreateFromIdAsync)
    during rvscan plugin activation. Whenever a host BlueZ radio exists, Wine's
    winebth driver exposes it, and those still-stubbed WinRT APIs return
    E_NOTIMPL; the exception escapes the plugin start and the app dies before
    showing its window. On radio-less hosts simpleble fails gracefully, so the
    fix is to never expose a radio: strip the bundled winebth driver (build
    time) and remove any staged driver or registration from existing prefixes.
    """
    prefix = Path(prefix)
    if not prefix.is_dir():
        return []
    removed: list[str] = []
    for relative in (
        "drive_c/windows/system32/drivers/winebth.sys",
        "drive_c/windows/syswow64/drivers/winebth.sys",
    ):
        staged = prefix / relative
        if staged.is_file():
            staged.unlink()
            removed.append(relative)

    reg_path = prefix / "system.reg"
    if reg_path.is_file():
        try:
            original = reg_path.read_text(encoding="utf-8", errors="surrogateescape")
        except OSError:
            return removed
        cleaned, dropped = _drop_winebth_sections(original)
        if dropped:
            reg_path.write_text(cleaned, encoding="utf-8", errors="surrogateescape")
            removed.append(f"system.reg ({dropped} sections)")
    return removed


def _drop_winebth_sections(content: str) -> tuple[str, int]:
    lines = content.splitlines(keepends=True)
    kept: list[str] = []
    dropped = 0
    skipping = False
    for line in lines:
        if line.startswith("["):
            skipping = (
                "\\Services\\winebth" in line
                or "\\Enum\\winebth" in line
                or ("winebth" in line and ("\\Services\\" in line or "\\Enum\\" in line))
            )
            if skipping:
                dropped += 1
                continue
        elif skipping:
            # Swallow value lines and their continuations. Blank lines belong
            # to no section; continuation lines end before the next header.
            if line.strip() == "":
                continue
            continue
        kept.append(line)
    return "".join(kept), dropped

