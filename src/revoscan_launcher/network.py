"""Host-firewall helpers for reaching a scanner from Revo Scan under Wine.

Revo Scan runs under Wine and shares the host network stack, so the scanner is
reachable through whichever interface the user attached to its access point or
LAN. Wi-Fi selection deliberately stays in the desktop's network settings: the
launcher only needs firewalld to accept the scanner's traffic. A default
firewalld zone silently drops inbound UDP from the scanner subnet, which breaks
discovery even though the app's sockets are bound and waiting.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import subprocess


def _run(args: list[str], timeout: float = 30.0) -> str:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        # Missing binary or timeout: report "no output" so callers can treat
        # firewalld as unavailable instead of crashing the UI thread.
        return ""


@dataclass(frozen=True)
class ScannerLink:
    device: str
    address: str
    cidr: str


def ipv4_links(runner=_run) -> list[ScannerLink]:
    """IPv4 addresses per interface, with host bits normalised into a CIDR."""
    out = runner(["ip", "-o", "-4", "addr", "show"])
    links: list[ScannerLink] = []
    for line in out.splitlines():
        fields = line.split()
        if "inet" not in fields or len(fields) < 2:
            continue
        device = fields[1].split("@")[0].rstrip(":")
        try:
            cidr_text = fields[fields.index("inet") + 1]
            address, _, prefix = cidr_text.partition("/")
            network = ipaddress.IPv4Network(cidr_text, strict=False)
            ipaddress.IPv4Address(address)
        except (IndexError, ValueError):
            continue
        if network.is_loopback:
            continue
        links.append(ScannerLink(device, address, str(network)))
    return links


def default_route_device(runner=_run) -> str | None:
    out = runner(["ip", "route", "show", "default"])
    for line in out.splitlines():
        fields = line.split()
        if "dev" in fields:
            return fields[fields.index("dev") + 1]
    return None


def scanner_subnets(runner=_run) -> list[ScannerLink]:
    """Subnets on interfaces that do not own the default route.

    A spare Wi-Fi adapter attached to the scanner lives here; the adapter that
    carries internet traffic is skipped so a LAN-wide rule is never added by
    accident.
    """
    default = default_route_device(runner)
    return sorted(
        (link for link in ipv4_links(runner) if link.device != default),
        key=lambda link: link.device,
    )


def rich_rule(cidr: str) -> str:
    network = ipaddress.IPv4Network(cidr.strip(), strict=False)
    return f'rule family="ipv4" source address="{network}" accept'


def parse_subnets(text: str) -> list[str]:
    """Normalise a comma/space separated subnet entry field."""
    values: list[str] = []
    for token in re.split(r"[\s,;]+", text.strip()):
        if not token:
            continue
        network = ipaddress.IPv4Network(token, strict=False)
        value = str(network)
        if value not in values:
            values.append(value)
    return values


def firewalld_state(runner=_run) -> str:
    out = runner(["firewall-cmd", "--state"], timeout=10).strip()
    return out or "unavailable"


def firewall_allows(cidr: str, runner=_run) -> bool:
    out = runner(["firewall-cmd", "--query-rich-rule=" + rich_rule(cidr)], timeout=15)
    return "yes" in out.lower()


def ensure_firewall_allows(address: str, runner=_run) -> tuple[bool, str]:
    """Make firewalld accept traffic from `address` (IP or CIDR).

    Tries passwordless sudo first; returns (applied, message) where the message
    carries the exact command to run when elevation was not possible.
    """
    rule = rich_rule(address)
    state = firewalld_state(runner)
    if state == "unavailable":
        return True, "No firewall installed — nothing to open."
    if state != "running":
        return True, "Firewall is off — no rule needed."
    if firewall_allows(address, runner):
        return True, f"Already allowed: {address}."
    for prefix_args in (["sudo", "-n"], []):
        out = runner(prefix_args + ["firewall-cmd", "--add-rich-rule=" + rule], timeout=30)
        if "success" in out.lower():
            runner(prefix_args + ["firewall-cmd", "--permanent", "--add-rich-rule=" + rule], timeout=30)
            return True, f"Allowed {address} (kept after reboot)."
    return False, (
        "Needs admin rights — run: sudo firewall-cmd --add-rich-rule='"
        f"{rule}' && sudo firewall-cmd --permanent --add-rich-rule='{rule}'"
    )


@dataclass(frozen=True)
class FirewallReport:
    """Whether scanner traffic can reach the host, for the GUI status label."""

    state: str
    allowed: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.missing

    def describe(self) -> str:
        if self.state == "unavailable":
            return "No firewall installed — nothing is blocking the scanner."
        if self.state != "running":
            return "Firewall is off — nothing is blocking the scanner."
        if not self.allowed and not self.missing:
            return (
                "Connect your spare Wi-Fi adapter to the scanner's access point, then check "
                "again — or type the scanner's network above."
            )
        if self.missing:
            joined = ", ".join(self.missing)
            return f"The firewall is blocking {joined}. Press ‘Allow scanner’."
        return "Firewall already allows " + ", ".join(self.allowed) + "."


def firewall_report(subnets: list[str], runner=_run) -> FirewallReport:
    state = firewalld_state(runner)
    if state != "running":
        return FirewallReport(state=state)
    allowed: list[str] = []
    missing: list[str] = []
    for cidr in subnets:
        (allowed if firewall_allows(cidr, runner) else missing).append(cidr)
    return FirewallReport(state=state, allowed=tuple(allowed), missing=tuple(missing))
