"""GPU discovery and explicit AMD-target mapping profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

VENDOR_NAMES = {
    0x1002: "amd",
    0x8086: "intel",
    0x10DE: "nvidia",
}


@dataclass(frozen=True)
class GpuAdapter:
    vendor_id: int
    device_id: int
    name: str
    pci_path: str = ""

    @property
    def vendor(self) -> str:
        return VENDOR_NAMES.get(self.vendor_id, "unknown")

    @classmethod
    def from_pci(cls, vendor: str | int, device: str | int, name: str, pci_path: str = ""):
        return cls(parse_pci_id(vendor), parse_pci_id(device), name.strip(), pci_path)

    @property
    def identity(self) -> str:
        return f"{self.vendor_id:04x}:{self.device_id:04x}"


@dataclass(frozen=True)
class GpuTarget:
    key: str
    name: str
    vendor_id: int = 0x1002


# These are selectable reported identities, not claims about real compute support.
AMD_TARGETS = {
    "rx-7700-xt": GpuTarget("rx-7700-xt", "AMD Radeon RX 7700 XT"),
    "rx-9070-xt": GpuTarget("rx-9070-xt", "AMD Radeon RX 9070 XT"),
    "rx-6750-gre": GpuTarget("rx-6750-gre", "AMD Radeon RX 6750 GRE"),
}


def parse_pci_id(value: str | int) -> int:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a PCI identifier")
    if isinstance(value, int):
        number = value
    else:
        text = value.strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        if not re.fullmatch(r"[0-9a-f]{1,4}", text):
            raise ValueError(f"Invalid 16-bit PCI identifier: {value!r}")
        number = int(text, 16)
    if not 0 <= number <= 0xFFFF:
        raise ValueError(f"PCI identifier out of range: {value!r}")
    return number


def detect_adapters(sysfs_root: Path = Path("/sys")) -> list[GpuAdapter]:
    """Read DRM PCI identities from sysfs without requiring lspci or Vulkan tools."""
    drm = Path(sysfs_root) / "class/drm"
    found: dict[tuple[int, int, str], GpuAdapter] = {}
    if not drm.is_dir():
        return []
    for device_dir in sorted(drm.glob("card[0-9]*/device")):
        try:
            vendor_id = parse_pci_id((device_dir / "vendor").read_text().strip())
            device_id = parse_pci_id((device_dir / "device").read_text().strip())
        except (OSError, ValueError):
            continue
        if vendor_id not in VENDOR_NAMES:
            continue
        label = ""
        for name_file in (device_dir / "product_name", device_dir / "label"):
            try:
                label = name_file.read_text().strip()
                if label:
                    break
            except OSError:
                pass
        if not label:
            label = f"{VENDOR_NAMES[vendor_id].title()} GPU {vendor_id:04x}:{device_id:04x}"
        try:
            pci_path = str(device_dir.resolve())
        except OSError:
            pci_path = str(device_dir)
        key = (vendor_id, device_id, pci_path)
        found[key] = GpuAdapter(vendor_id, device_id, label, pci_path)
    return list(found.values())


def build_mapping_environment(
    source: GpuAdapter,
    target: GpuTarget | None,
) -> dict[str, str]:
    """Return opt-in Vulkan layer settings; empty mapping means no spoofing."""
    if target is None:
        return {}
    if source.vendor not in {"amd", "intel"}:
        raise ValueError("Only AMD and Intel source adapters have mapping profiles.")
    if target.vendor_id != 0x1002 or target.key not in AMD_TARGETS:
        raise ValueError("Target must be one of the built-in AMD profiles.")
    return {
        "REVOSCAN_MAP_SOURCE_VENDOR": f"{source.vendor_id:04x}",
        "REVOSCAN_MAP_SOURCE_DEVICE": f"{source.device_id:04x}",
        "REVOSCAN_MAP_TARGET_VENDOR": f"{target.vendor_id:04x}",
        "REVOSCAN_MAP_TARGET_NAME": target.name,
    }
