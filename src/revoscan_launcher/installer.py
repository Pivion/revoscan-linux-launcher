"""Safe discovery and download of user-requested official installers."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import ssl
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

SUPPORT_PAGE = "https://www.revopoint3d.com/pages/support-download"
DOWNLOAD_HOST = "dl.revopoint3d.com"
MAX_INSTALLER_BYTES = 2 * 1024 * 1024 * 1024
_INSTALLER_RE = re.compile(
    r"^RevoScan6-(?P<version>[0-9]+(?:\.[0-9]+){1,3})-windows-x86_64\.exe$",
    re.IGNORECASE,
)


def default_ca_bundle() -> str | None:
    """Use the bundled certifi roots when available; otherwise use OS roots."""
    try:
        import certifi
    except ImportError:
        return None
    return certifi.where()


def create_https_context() -> ssl.SSLContext:
    """Create a verifying TLS context independent of the build distro's CA path."""
    return ssl.create_default_context(cafile=default_ca_bundle())


class InstallerError(RuntimeError):
    """Raised when a candidate installer is unsafe or cannot be downloaded."""


@dataclass(frozen=True)
class OfficialInstaller:
    version: str
    url: str

    @property
    def version_key(self) -> tuple[int, ...]:
        return tuple(int(part) for part in self.version.split("."))


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value.strip())


def validate_installer_url(url: str) -> bool:
    """Accept only direct HTTPS x86_64 installer links on Revopoint's CDN."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https" or parsed.hostname != DOWNLOAD_HOST:
            return False
        if parsed.port not in (None, 443) or parsed.username or parsed.password:
            return False
        path = parsed.path
        if not path.startswith("/softs/revoscan6/"):
            return False
        return _INSTALLER_RE.fullmatch(Path(path).name) is not None
    except (ValueError, TypeError):
        return False


def discover_official_installers(
    html: str,
    base_url: str = SUPPORT_PAGE,
) -> list[OfficialInstaller]:
    """Extract direct official x86_64 Revo Scan 6 installers, newest first."""
    parser = _AnchorParser()
    parser.feed(html)
    releases: dict[str, OfficialInstaller] = {}
    for href in parser.hrefs:
        url = urljoin(base_url, href)
        if not validate_installer_url(url):
            continue
        filename = Path(urlparse(url).path).name
        match = _INSTALLER_RE.fullmatch(filename)
        if not match:
            continue
        version = match.group("version")
        releases[url] = OfficialInstaller(version=version, url=url)
    return sorted(releases.values(), key=lambda item: item.version_key, reverse=True)


def fetch_latest_official_installer(timeout: float = 25.0) -> OfficialInstaller:
    """Fetch the vendor support page and return its highest advertised version."""
    request = Request(
        SUPPORT_PAGE,
        headers={"User-Agent": "RevoScanLinuxLauncher/0.1 (+official-download-discovery)"},
    )
    with urlopen(request, timeout=timeout, context=create_https_context()) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in {
            "revopoint3d.com",
            "www.revopoint3d.com",
        }:
            raise InstallerError("The support page redirected away from Revopoint HTTPS.")
        html = response.read(8 * 1024 * 1024 + 1)
        if len(html) > 8 * 1024 * 1024:
            raise InstallerError("The support page exceeded the safe 8 MiB limit.")
    releases = discover_official_installers(html.decode("utf-8", errors="replace"), response.geturl())
    if not releases:
        raise InstallerError(
            "No direct x86_64 installer link was found on the official page. "
            "Open the page and select the downloaded installer manually."
        )
    return releases[0]


def download_official_installer(
    release: OfficialInstaller,
    destination: Path,
    *,
    max_bytes: int = MAX_INSTALLER_BYTES,
    progress=None,
    timeout: float = 60.0,
) -> Path:
    """Download an explicitly chosen official installer with redirect/size checks."""
    if not validate_installer_url(release.url):
        raise InstallerError("Refusing a non-official or malformed installer URL.")
    filename_match = _INSTALLER_RE.fullmatch(Path(urlparse(release.url).path).name)
    if not filename_match or filename_match.group("version") != release.version:
        raise InstallerError("Release version does not match the official installer filename.")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    request = Request(
        release.url,
        headers={"User-Agent": "RevoScanLinuxLauncher/0.1 (user-initiated download)"},
    )
    total = 0
    try:
        with urlopen(request, timeout=timeout, context=create_https_context()) as response:
            if not validate_installer_url(response.geturl()):
                raise InstallerError("Installer redirect left the official Revopoint CDN.")
            declared = response.headers.get("Content-Length")
            expected = int(declared) if declared and declared.isdigit() else None
            if expected is not None and expected > max_bytes:
                raise InstallerError("Installer exceeds the configured size limit.")
            with partial.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise InstallerError("Installer exceeded the configured size limit.")
                    output.write(chunk)
                    if progress:
                        progress(total, expected)
                output.flush()
                os.fsync(output.fileno())
            if expected is not None and total != expected:
                raise InstallerError("Downloaded size did not match the server's Content-Length.")
        os.replace(partial, destination)
        return destination
    except Exception:
        partial.unlink(missing_ok=True)
        raise
