"""Scanner Wi-Fi discovery and connection via nmcli.

Revopoint scanners (POP series, MIRACO) expose an access point whose SSID
looks like ``POP4-REVO-D2682977``. The launcher connects a spare Wi-Fi adapter
to that AP so Revo Scan (running under Wine, sharing the host network stack)
can reach the scanner while the primary adapter keeps internet access. The
scanner connection is marked ``never-default`` so it never hijacks the host
default route.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess

SCANNER_SSID_PATTERN = re.compile(r"revo|revopoint|miraco|pop\s?\d", re.IGNORECASE)


def is_scanner_ssid(ssid: str) -> bool:
    """Match known Revopoint AP naming (POP4-REVO-…, MIRACO-…).

    This is a hint, not a requirement: any open (security-less) AP is treated
    as a scanner candidate, since compatible scanners may use other SSIDs.
    """
    return bool(ssid) and bool(SCANNER_SSID_PATTERN.search(ssid))


def is_scanner_candidate(network: WifiNetwork) -> bool:
    """A vendor-named SSID, or any open network a scanner could expose."""
    return is_scanner_ssid(network.ssid) or network.security == ""


@dataclass(frozen=True)
class WifiNetwork:
    ssid: str
    bssid: str
    security: str
    signal: int
    channel: int

    @property
    def is_scanner(self) -> bool:
        return is_scanner_ssid(self.ssid)


@dataclass(frozen=True)
class WifiDevice:
    device: str
    state: str
    connection: str


def _run(args: list[str], timeout: float = 30.0) -> str:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    ).stdout


def wifi_devices(runner=_run) -> list[WifiDevice]:
    out = runner(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    devices: list[WifiDevice] = []
    for line in out.splitlines():
        fields = line.split(":")
        if len(fields) < 4:
            continue
        device, dev_type, state = fields[0], fields[1], fields[2]
        connection = ":".join(fields[3:])
        if dev_type != "wifi" or device.startswith("p2p-"):
            continue
        devices.append(WifiDevice(device, state, connection))
    return devices


def scan_networks(device: str | None = None, runner=_run) -> list[WifiNetwork]:
    args = ["nmcli", "-t", "-f", "SSID,BSSID,SECURITY,SIGNAL,CHAN", "device", "wifi", "list"]
    if device:
        args += ["ifname", device]
    out = runner(args)
    networks: dict[str, WifiNetwork] = {}
    for line in out.splitlines():
        # nmcli -t emits 5 fields; literal colons (BSSID, SSID) are "\:"-escaped, so
        # placeholder them out before splitting.
        fields = [field.replace("\x00", ":") for field in line.replace("\\:", "\x00").split(":")]
        if len(fields) < 5:
            continue
        ssid, bssid, security, signal, channel = fields[:5]
        if not ssid:
            continue
        try:
            signal_value = int(signal)
            channel_value = int(channel)
        except ValueError:
            continue
        network = WifiNetwork(ssid, bssid, security, signal_value, channel_value)
        previous = networks.get(ssid)
        # Keep the strongest BSSID per SSID.
        if previous is None or signal_value > previous.signal:
            networks[ssid] = network
    return sorted(networks.values(), key=lambda net: -net.signal)


def find_scanner_network(networks: list[WifiNetwork]) -> WifiNetwork | None:
    candidates = [net for net in networks if is_scanner_candidate(net)]
    return max(candidates, key=lambda net: (is_scanner_ssid(net.ssid), net.signal), default=None)


def scanner_candidates(networks: list[WifiNetwork]) -> list[WifiNetwork]:
    """Candidate scanner APs, vendor-named first, then strongest open APs."""
    return sorted(
        (net for net in networks if is_scanner_candidate(net)),
        key=lambda net: (is_scanner_ssid(net.ssid), net.signal),
        reverse=True,
    )


def _uuid_for_device(device: str, runner=_run) -> str | None:
    out = runner(["nmcli", "-t", "-f", "DEVICE,UUID", "connection", "show", "--active"])
    for line in out.splitlines():
        fields = line.split(":")
        if len(fields) >= 2 and fields[0] == device:
            return fields[1]
    return None


def make_connection_never_default(device: str, runner=_run) -> bool:
    """Stop the scanner connection from owning the host default route."""
    uuid = _uuid_for_device(device, runner)
    if not uuid:
        return False
    runner(["nmcli", "connection", "modify", uuid, "ipv4.never-default", "yes"])
    runner(["nmcli", "connection", "modify", uuid, "ipv6.never-default", "yes"])
    return True


def connect_network(device: str, ssid: str, runner=_run, secret: str | None = None) -> bool:
    args = ["nmcli", "device", "wifi", "connect", ssid, "ifname", device]
    if secret:
        args += ["password", secret]
    out = runner(args)
    ok = "successfully activated" in out
    if ok:
        make_connection_never_default(device, runner)
    return ok


def default_route_device(runner=_run) -> str | None:
    out = runner(["ip", "route", "show", "default"])
    for line in out.splitlines():
        fields = line.split()
        if "dev" in fields:
            return fields[fields.index("dev") + 1]
    return None


def scanner_reachable(address: str, runner=_run) -> bool:
    out = runner(["ping", "-c", "1", "-W", "2", address])
    return " 0% packet loss" in out


def device_gateway(device: str, runner=_run) -> str | None:
    out = runner(["nmcli", "-t", "-f", "IP4.GATEWAY", "device", "show", device])
    for line in out.splitlines():
        value = line.split(":", 1)[1].strip() if ":" in line else ""
        if value:
            return value
    return None


def _firewall_rich_rule(address: str) -> str:
    return f'rule family="ipv4" source address="{address}/32" accept'


def firewalld_state(runner=_run) -> str | None:
    out = runner(["firewall-cmd", "--state"], timeout=10)
    return out.strip() or None


def firewall_allows(address: str, runner=_run) -> bool:
    out = runner(["firewall-cmd", "--query-rich-rule=" + _firewall_rich_rule(address)], timeout=15)
    return "yes" in out.lower()


def ensure_firewall_allows(address: str, runner=_run) -> tuple[bool, str]:
    """Make firewalld accept traffic from `address`.

    Device discovery UDP from scanner APs is otherwise silently dropped by a
    default-zone firewalld even though the app's sockets are bound. Tries a
    passwordless sudo first; returns (applied, message) where message carries
    the exact command to run when elevation was not possible.
    """
    rule = _firewall_rich_rule(address)
    import shutil

    if shutil.which("firewall-cmd") is None:
        return True, "firewalld not installed; nothing to allow."
    if firewalld_state(runner) != "running":
        return True, "firewalld not active; nothing to allow."
    if firewall_allows(address, runner):
        return True, "firewalld already allows this address."
    for prefix_args in (["sudo", "-n"], []):
        out = runner(prefix_args + ["firewall-cmd", "--add-rich-rule=" + rule], timeout=30)
        if "success" in out.lower():
            runner(prefix_args + ["firewall-cmd", "--permanent", "--add-rich-rule=" + rule], timeout=30)
            return True, f"firewalld now allows {address} (rule persisted)."
    return False, f"Elevation required — run: sudo firewall-cmd --add-rich-rule='{rule}' && sudo firewall-cmd --permanent --add-rich-rule='{rule}'"