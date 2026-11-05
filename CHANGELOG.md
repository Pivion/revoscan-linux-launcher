# Changelog

## 0.1.3 — 2026-11-06

Launcher

- Scanner setup is now one button: the launcher detects the scanner's subnet on your spare Wi-Fi adapter, adds the firewalld rule (runtime + permanent) and shows whether traffic is already allowed. Scanning for and connecting Wi-Fi networks inside the launcher is gone — connect the adapter in your desktop's network settings.
- The firewall status is only checked when you press *Check status*, so opening the launcher no longer triggers a password prompt.
- GPU mapping now works: mapping also switches Wine to its Vulkan renderer, which is what Revo Scan's GPU check reads. Revo Scan lists the selected AMD card and enables GPU acceleration.
- New *Test* button shows exactly what Revo Scan will be told about your GPU.
- Mapping is not claimed when the layer is unavailable; Revo Scan starts unmapped and the status says so.
- `python -m revoscan_launcher` now honours `--check-wine`, `--vulkan-check` and `--check-latest-installer` instead of starting the GUI.
- Rewritten window copy and README: usage-first, shorter labels, no implementation detail.

Packaging

- The Vulkan layer manifest uses a manifest-relative `./librevoscan_gpu_map.so` path; a bare name failed to load in some launcher/Wine environments.
- `VK_LAYER_PATH` is only set when the layer manifest and library are both present.
- Build script takes the version from `pyproject.toml` and writes `dist/RevoScan-Linux-Launcher-<version>-x86_64.AppImage`.

Known limits

- Bluetooth scanner discovery does not work under Wine; Wi-Fi and USB are unaffected.
- Preview build: distro coverage is still Ubuntu 22.04-built-with-host-drivers only.
