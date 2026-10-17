# RevoScan Linux Launcher

An unofficial, community-built AppImage launcher for running Revopoint's Windows Revo Scan 6 on Linux through Wine. It is not affiliated with or supported by Revopoint.

## Public-release boundary

A published AppImage may contain the launcher, Wine, this project's open-source Vulkan compatibility layer, and their license notices. **It must never contain Revopoint's installer or application binaries, a Wine prefix with Revo Scan installed, activation/account data, scan projects, serial numbers, or logs.** The user must select a Windows installer or explicitly download one from Revopoint's official support page, then accept the vendor's terms themselves. The official pages currently expose Windows x86_64 downloads; this project is an unofficial Wine wrapper, not a native Linux port.[1][2]

The public release must be reproducible from tracked source. Machine-specific proof builds and vendor installers are kept only under ignored `local/` paths. Check `.gitignore` before adding build artifacts.

## Intended first-run flow

1. Start the launcher GUI; do not start Revo Scan directly.
2. Choose a local `RevoScan6-*-windows-x86_64.exe`, or ask the launcher to discover and download the current Windows installer link from the official Revopoint support page. Show the advertised version, final URL, size/progress, and confirmation before downloading. Reject non-HTTPS or non-Revopoint download hosts. TLS uses the bundled certifi root bundle; certificate verification is never disabled.
3. Create a writable per-user Wine prefix, run the installer interactively, and leave all EULA/activation decisions to the user.
4. Detect Vulkan-capable AMD and Intel adapters. GPU identity mapping is **off by default** and requires explicit selection and a warning acknowledgement. The initial targets are Revopoint's published GPU compatibility-test identities (RX 7700 XT, RX 9070 XT, RX 6750 GRE); the shim changes reported identity only and does not add hardware capability.[2]
5. Launch the installed Revo Scan through the managed Wine runtime with the selected mapping. Keep the original Wine prefix and user projects untouched.

## GPU mapping safety

The mapper is an experimental compatibility workaround, not an upgrade, benchmark, or guarantee of acceleration. It must report actual adapter vendor/device/driver separately from the selected reported AMD target. No target is presumed compatible just because the allowlist accepts its name. Intel-to-AMD mapping is not validated until tested on physical Intel hardware. Provide a no-spoof option and a clear reset path.

## Cross-distro target

Target families are Ubuntu, Debian, Fedora, openSUSE, and Arch Linux (x86_64). A release is **not** cross-distro supported until its AppImage has been tested on pinned versions from each family. AppImage guidance recommends building on the oldest target base, bundling non-baseline dependencies, and testing on the intended systems; merely producing an AppImage does not establish portability.[3][4][5]

The existing local Revo Scan 6.4.1 proof AppImage was built on this Fedora-derived machine and contains proprietary software. It is a private legacy artifact only; it is not the project release and must never be uploaded or committed.

## Development

```bash
python -m unittest discover -s tests -v
```

See [AGENTS.md](AGENTS.md), [PROGRESS.md](PROGRESS.md), and `docs/` before changing packaging, installer download, or GPU mapping behavior.

## Status

A public-clean x86_64 preview AppImage is built at `dist/RevoScan-Linux-Launcher-0.1.1-x86_64.AppImage` (about 412 MB). It starts the launcher first and contains Wine 11.0 Staging, the launcher, bundled certifi roots, the opt-in Vulkan layer, and notices—but no Revo Scan software or installer. The official download resolver returns the currently advertised 6.4.1.1088 link; the installer itself was not downloaded.[1]

The run-installer button refreshes after selecting a valid local installer or after a successful download. The packaged `--check-latest-installer` diagnostic verifies bundled CA roots; `--check-wine` checks the bundled Wine executable without touching the user's prefix. AppRun now preserves the host library path separately, so Wine and desktop openers do not inherit PyInstaller's temporary libraries. The Ubuntu 22.04 Xvfb smoke and public-payload audit pass; Python and C tests pass. Debian 12 had a partial launcher/Wine prefix smoke. Fedora 44, openSUSE, and Arch still need target testing; this is not yet a verified “works on any distro” release and has not been uploaded.

## Sources

[1] https://revopoint3d.com/pages/support-download — Revopoint Support Download
[2] https://revopoint3d.com/pages/revo-scan-6 — Revo Scan 6
[3] https://docs.appimage.org/introduction/concepts.html — AppImage Concepts
[4] https://docs.appimage.org/reference/best-practices.html — AppImage Best Practices
[5] https://docs.appimage.org/packaging-guide/testing.html — AppImage Testing
