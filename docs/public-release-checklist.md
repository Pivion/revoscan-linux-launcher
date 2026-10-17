# Public release checklist

- [ ] AppImage opens the launcher first.
- [ ] Public payload contains no Revo Scan installer, application files, installed prefix, activation state, scan projects, logs, serials, or credentials.
- [ ] User explicitly selects a local installer or confirms an official-page download.
- [ ] Installer URL uses HTTPS, comes from the official Revopoint support page, and final redirect host is allowlisted.
- [ ] EULA and activation remain user-controlled.
- [ ] GPU identity mapping is opt-in, reversible, and defaults to disabled.
- [ ] UI separates actual adapter/driver from spoofed AMD target and warns that identity spoofing adds no capabilities.
- [ ] AMD, Intel, and no-spoof choices are validated; Intel only called tested after physical Intel hardware coverage.
- [ ] License and source notices for every bundled dependency are included.
- [ ] AppImage built on the oldest pinned target and smoke-tested on all advertised families.
- [ ] Real GPU and POP 4 scan/fusion/export tested; otherwise mark those features unverified.
- [ ] Run `scripts/audit-public-artifact.py` against the AppDir and release file.
- [ ] Review `git status --short`; verify no files under `local/` are tracked.
