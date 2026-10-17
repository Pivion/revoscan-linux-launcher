# Agent instructions

## Project goal
Build a public, reproducible x86_64 AppImage that starts a launcher GUI first, lets the user provide or download the official Revo Scan Windows installer, installs/runs it under bundled Wine, and offers explicit AMD/Intel-source to AMD-target Vulkan identity mappings.

## Public distribution rules (mandatory)
- Never add the proprietary Revopoint installer, installed Revo Scan files, Wine prefixes containing Revo Scan, activation/account data, user scans, device serials, credentials, or runtime logs to tracked source or public artifacts.
- Keep local/private assets under `local/` (ignored). Keep generated AppImages under `dist/` (ignored); publish only after a public-content audit.
- The launcher may fetch installers only after user action. Use HTTPS; select links from Revopoint's official support page; validate the final redirect host and installer filename; show the version, URL, size, and confirmation. Do not silently run a downloaded installer.
- Never accept license terms, activate a device, or enter credentials on the user's behalf.
- Ship complete license notices and corresponding source for Wine, the Vulkan layer, and other bundled open-source components.

## Engineering rules
- Follow strict TDD: write a focused failing test, run it to observe RED, implement the smallest change, observe GREEN, then run the full suite.
- Use standard-library Python for launcher logic when practical. Keep UI code thin and dependency-injected so installer, mapping, and command construction can be tested without a display.
- Do not enable GPU spoofing by default. Keep an unmodified path, explicit per-adapter selection, validation, and a reversible configuration. Show the physical adapter and the reported target separately.
- Intel-to-AMD mappings are experimental until exercised on physical Intel Vulkan hardware. Never equate passing Revo Scan's filter with actual compute compatibility.
- Build the public AppImage on the oldest pinned target distribution, avoid newer-than-target GLIBC/libstdc++ symbols, use host GPU drivers, and test actual startup on each advertised distro. Container-only success is not full desktop/GPU validation.
- Keep AppImage/PyInstaller `LD_LIBRARY_PATH` out of host desktop openers and Wine child processes. `AppRun` must preserve the host's original library path separately; `runtime.py` should add only Wine/Vulkan-layer directories plus that host path so frozen Python libraries cannot shadow newer distro libraries.
- Do not package Fedora-specific Wine binaries and call the result universal without a baseline ABI test.
- Update `PROGRESS.md` after each completed milestone with accomplished, in-progress, and roadmap sections. Record evidence and failures; don't overstate portability.

## Working-tree hygiene
- Read existing files before editing them. Keep the repository's public source clean of local outputs.
- Run `python -m unittest discover -s tests -v` after code changes.
- Run the repository's public-artifact audit before any release; it must fail on proprietary installer signatures, local prefixes, logs, scan formats, or private serials.
- Ask before changing system udev rules or installing host packages requiring administrator privileges.
