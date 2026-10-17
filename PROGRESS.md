# Progress

## Accomplished
- Created the public project repository at `~/Projects/revoscan-linux-launcher` with `README.md`, `AGENTS.md`, `.gitignore`, release checklist, cross-distro matrix, source, and tests.
- Established a strict public boundary: the AppImage must not contain Revo Scan binaries, installer, installed prefix, activation data, logs, or scan projects.
- Consolidated the previous proprietary proof AppImage, AppDir, installer cache, and test prefix under Git-ignored `local/`; removed disposable AppImage test prefixes and old probe files. The original Wine prefix was left untouched.
- Implemented a Tk launcher-first GUI with local installer selection, explicit-confirmation download from Revopoint's official HTTPS CDN, per-user Wine prefix, AMD/Intel adapter selection, AMD target profiles, and mapping disabled by default.
- Fixed installer button state refresh after selection and after successful download. Added unit coverage for valid/missing installer paths.
- Fixed cross-distro CA verification by bundling certifi roots and passing an explicit verifying SSL context. The packaged diagnostic returned official Revo Scan 6.4.1.1088 even when `SSL_CERT_FILE=/nonexistent`; no installer was downloaded.
- Fixed AppImage library-path leakage: AppRun now preserves the original host `LD_LIBRARY_PATH`; Wine children exclude PyInstaller's `_MEI` libraries. Desktop openers run with host libraries only. The Ultramarine reproduction failed with `OPENSSL_3.2.0/3.5.0 not found` under the polluted environment and `xdg-open` returned 0 after sanitization.
- Implemented configurable Vulkan property mapping. The C layer passed tests for AMD/Intel source matching, opt-in behavior, and preserving the actual PCI device ID. A live `vulkaninfo` run on this Radeon 780M showed the selected RX 7700 XT identity and discrete type.
- Built `dist/RevoScan-Linux-Launcher-0.1.1-x86_64.AppImage` from Ubuntu 22.04 / glibc 2.35. It starts the launcher first and contains Wine 11.0 Staging, the launcher, certifi, and the mapping layer—not Revopoint software. Final size: 412,129,784 bytes; SHA-256: `b12e8444387dd0336dafcefc62f76f2705b654d1d4971ce1f76ee3ff3e310d4c`. Audit and Ubuntu 22.04 Xvfb smoke passed. The 0.1.1 AppImage was copied to Pop!_OS Downloads; bundled Wine check and HTTPS resolver both passed there, including with `SSL_CERT_FILE=/nonexistent`. The earlier 0.1.0 file/process was left untouched.
- AppImage public-payload audit passed. Ubuntu 22.04 Xvfb launcher smoke passed. Debian 12 container smoke created a 64-bit Wine prefix and started the GUI, but emitted missing host Vulkan/display warnings because the test container had no graphics driver.
- Current tests: 23 Python unit tests and the C GPU-property-map test suite pass.

## In progress
- Complete the distro matrix with pinned Ubuntu, Debian, Fedora, openSUSE, and Arch environments; the current artifact is still experimental.
- Resolve/characterize the Fedora 44 container WineBoot smoke timeout and test on a full Fedora desktop with host graphics libraries.
- Investigate the Revo Scan no-window failure on Pop!_OS. Under bundled Wine 11.0 and system Wine, RevoScan6 creates a main X11 window that stays unmapped; bundled launches later generated Crashpad dumps with exception `0xe06d7363`. Bundled-Wine Notepad maps normally. Forcing X11, Wine virtual desktop, software OpenGL, and a temporary OpenGL renderer setting did not make Revo Scan visible; the renderer config was restored. No reliable app workaround is confirmed.
- Test the packaged UI's manual installer and confirmed-download paths end-to-end without downloading or installing on the user's behalf.
- Validate Intel mapping on physical Intel Vulkan hardware; current real-hardware test covers the AMD Radeon 780M only.

## Roadmap
1. Finish runtime smoke tests on all target distro families and pin the minimum supported releases.
2. Test Revo Scan install, scanner detection, capture, fusion, and export on supported host GPU/USB paths.
3. Review upstream Wine/AppImage/runtime licenses and make corresponding source/build provenance available for a public release.
4. Add release automation, signed checksums, and a final public-payload audit; publish only after the matrix and legal checklist pass.

## Known issues and limitations
- Fedora 44 container testing timed out during WineBoot; this is not a pass. openSUSE and Arch are untested.
- The Debian 12 test had no Vulkan driver; it cannot validate GPU mapping or scanning.
- Intel-to-AMD identity mapping is unverified on physical Intel hardware. A successful identity-filter check does not guarantee compute support.
- No complete Revo Scan scan/fusion/export has been completed. On Pop!_OS, RevoScan6's main X11 window remains unmapped under both bundled and system Wine. A bundled launch later exited with a Crashpad minidump reporting `0xe06d7363`; system-Wine runs can remain alive while the window is still unmapped. Notepad maps normally under bundled Wine. The temporary `ogre.cfg` renderer change was reverted; no user configuration change remains.
- The final AppImage is a preview build, not a published release. It uses the host graphics stack and device permissions.
