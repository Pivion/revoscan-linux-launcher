# Cross-distro release matrix

No distro family is yet marked fully supported. Pin concrete image tags and record kernel, libc, graphics stack, and test result before release. The current build baseline is Ubuntu 22.04 / glibc 2.35.

| Family | Planned pinned smoke test | Launcher GUI | Wine prefix | Vulkan / scan | State |
|---|---|---|---|---|---|
| Ubuntu | 22.04 builder image + Xvfb | passed | not fully tested | no GPU | partial |
| Debian | 12 slim + Xvfb | passed | 64-bit prefix created; container lacked Vulkan/desktop driver | no GPU | partial |
| Pop!_OS | 24.04 desktop; 0.1.1 AppImage | CLI Wine/TLS checks pass | RevoScan6's X11 window remains unmapped under system and bundled Wine; a bundled run later exited with Crashpad exception `0xe06d7363`; bundled Notepad maps normally | POP 4 detected by an earlier system-Wine run; no scan | failed for Revo Scan UI |
| Fedora | 44 container + Xvfb | timed out during WineBoot | inconclusive | no GPU | not passed |
| openSUSE | pinned Leap image + Xvfb | not run | not run | not run | untested |
| Arch Linux | pinned image + Xvfb | not run | not run | not run | untested |

The AppImage was built on Ubuntu 22.04 to lower the glibc baseline. A preview binary launching on one distro does not establish compatibility across all target families; AppImage guidance calls for target-specific builds and tests.[3][4][5]

## Required checks per target

- AppImage runtime extraction and launcher startup.
- Launcher opens before Wine/Revo Scan; no automatic installer launch.
- Bundled 64-bit Wine ELF dependencies resolve on the target baseline.
- Host Vulkan loader and driver remain host-provided; enumerate actual adapters without substituting host graphics libraries.
- Download flow accepts only official HTTPS URLs, uses the bundled CA bundle, and enforces installer-size limits.
- Local installer path and existing user prefix are handled without overwriting user data.
- Intel mapping is reported as experimental until physical Intel Vulkan hardware reaches Revo Scan's GPU backend.
- At least one complete POP 4 scan/fusion/export on each supported GPU mapping before claiming scanning success.
