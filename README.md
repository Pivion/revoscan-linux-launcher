# Revo Scan on Linux

An unofficial launcher that runs Revopoint's Windows **Revo Scan 6** on Linux. Wine is built in, so you don't need to install or configure it.

Not affiliated with, endorsed by, or supported by Revopoint.

## What it does for you

- Installs and starts Revo Scan from one window — Wine included.
- Finds the current Windows installer on Revopoint's site and downloads it after you confirm, or uses an installer you already have.
- Adds the firewall rule that lets Revo Scan see your scanner, with a button instead of a terminal command.
- Optionally reports your graphics card to Revo Scan as a supported AMD card, if Revo Scan refuses to use the real one.

## Before you start

- A 64-bit Linux desktop with working Vulkan graphics drivers.
- NetworkManager for Wi-Fi, and firewalld if you want the firewall button to work.
- Around 1 GB of free space for the launcher, Wine and Revo Scan.

## Using it

1. **Start the launcher.** Everything happens from this window.
2. **Get the installer.** Pick a `RevoScan6-…-windows-x86_64.exe` you already have, or press *Download latest from Revopoint*. It shows the version and URL and asks before downloading. You accept Revopoint's licence yourself.
3. **Install.** Press *Install Revo Scan* and complete the setup window that opens.
4. **Connect the scanner.** Power the scanner on in Wi-Fi AP mode, connect your spare Wi-Fi adapter to its network in your desktop's network settings, then press *Allow scanner*. *Check status* shows whether the firewall is still blocking it.
5. **Scan.** Press *Launch Revo Scan*.

Your Revo Scan installation and settings live in `~/.local/share/revoscan-linux-launcher`. *Open data folder* takes you there.

## If Revo Scan says your GPU is unsupported

Open section 3, tick **Report GPU as**, choose the AMD card from the list, press **Test** to see what Revo Scan will be told, then launch.

This changes only what the app is told about your GPU. It does not add memory, speed or features, and it can cause instability.

## If something goes wrong

| Problem | What to try |
| --- | --- |
| Scanner isn't found | Make sure the spare Wi-Fi adapter is connected to the scanner's network, then press *Check status* → *Allow scanner*. |
| *Allow scanner* asks for a password | Adding a firewall rule needs admin rights — that prompt is normal. |
| *Download latest* fails | Press *Revopoint download page* and download the installer in your browser, then choose it with *Choose installer*. |
| Windows installer won't start | Make sure the file is the `windows-x86_64` build from Revopoint, not a macOS or ARM build. |

Known limits:

- Bluetooth scanner discovery does not work, because Wine doesn't implement the Windows Bluetooth APIs Revo Scan uses. Wi-Fi and USB connections are unaffected.
- This is a preview build. Scan quality and distro support are still being tested.

## What isn't included

The launcher, its AppImage and this repository contain **no Revopoint software**: no installer, no installed Revo Scan files, no activation data, no scan projects, no serial numbers and no logs. You supply the installer and accept Revopoint's terms yourself.

## Status

Latest build: **0.1.3** (preview) — `RevoScan-Linux-Launcher-0.1.3-x86_64.AppImage`, 411,826,680 bytes.

```
SHA-256  37e10be9483e0bd3c3b594cabcc21844e037e7a753e7efbbbfc8a1a51d3b6b38
```

Built on Ubuntu 22.04 (glibc 2.35) with Wine 11.0 Staging and the Vulkan mapping layer; contains no Revopoint software. Passed the public-payload audit, a containerised GUI smoke test, and `--check-wine` / `--vulkan-check` on a Fedora 44 host (Intel GPU, mapping applied). Other distros are still untested — see [PROGRESS.md](PROGRESS.md).

## Development

```bash
python -m unittest discover -s tests -v
bash tests/run-c-tests.sh
```

Build, packaging and release rules are in [AGENTS.md](AGENTS.md), status and evidence in [PROGRESS.md](PROGRESS.md), and packaging notes in `packaging/README.md` and `docs/`.
