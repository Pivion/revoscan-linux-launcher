Revo Scan on Linux 0.1.3 — first build where GPU acceleration actually works.

**Highlights**

- **GPU mapping works end to end.** If Revo Scan rejects your graphics card, the launcher can report it as a supported AMD card. Revo Scan now lists it and enables GPU acceleration (verified with Revo Scan 6.4.2 on an Intel GPU mapped to AMD Radeon RX 7700 XT, scanner streaming at 78 fps).
- **One-button scanner firewall.** The launcher detects the scanner's network on your spare Wi-Fi adapter and allows it through firewalld (kept after reboot). No terminal needed.
- **No password prompt until you ask.** Firewall status is checked only when you press *Check status*.
- **Simpler, shorter UI and README**, written around what you do rather than how it works.

**What you do**

1. Start the AppImage.
2. Choose your Revo Scan installer, or press *Download latest from Revopoint*. You accept Revopoint's licence yourself.
3. Press *Install Revo Scan* and finish the setup window.
4. Put the scanner in Wi-Fi AP mode, connect a spare Wi-Fi adapter to its network in your desktop settings, press *Allow scanner*.
5. Press *Launch Revo Scan*.

If Revo Scan says your GPU is unsupported: section 3 → tick *Report GPU as* → pick a card → *Test* → launch.

**Included**

`RevoScan-Linux-Launcher-0.1.3-x86_64.AppImage` — 411,826,680 bytes
SHA-256 `37e10be9483e0bd3c3b594cabcc21844e037e7a753e7efbbbfc8a1a51d3b6b38`

Contains Wine 11.0 Staging, the launcher, its Python/Tk runtime, bundled CA roots and the open-source Vulkan mapping layer — no Revopoint software, installer, prefix, licence data or scans.

**Known limits**

- Bluetooth scanner discovery doesn't work under Wine. Wi-Fi and USB are unaffected.
- Preview quality: built and smoke-tested on Ubuntu 22.04, run on Fedora 44; other distros are untested.
- Mapping changes what the app is told about your GPU, not what your GPU can do. It can be unstable; keep it off unless you need it.

**Changes since 0.1.2**

- Scanner Wi-Fi scanning/connecting removed; firewall button + status added.
- GPU mapping fixed: layer manifest path, stale bundled layer, and Wine's wined3d renderer switch so Revo Scan's GPU check sees the mapped device.
- `--vulkan-check` / `--check-wine` now work from a source checkout.
- Full list in [CHANGELOG.md](CHANGELOG.md).
