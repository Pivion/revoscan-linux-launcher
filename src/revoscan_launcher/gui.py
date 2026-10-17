"""Tk launcher UI; business logic lives in installer/gpu/runtime modules."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from .gpu import AMD_TARGETS, GpuAdapter, GpuTarget, detect_adapters
from .installer import (
    SUPPORT_PAGE,
    download_official_installer,
    fetch_latest_official_installer,
)
from .runtime import build_revoscan_environment, installed_executable, sanitize_bluetooth


def desktop_opener_environment(base_env: dict[str, str] | None = None) -> dict[str, str]:
    """Keep AppImage/PyInstaller libraries from shadowing the host file manager."""
    env = dict(os.environ if base_env is None else base_env)
    for key in (
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "PYTHONHOME",
        "PYTHONPATH",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
    ):
        env.pop(key, None)
    return env


class Launcher:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Revo Scan for Linux — unofficial launcher")
        self.root.geometry("780x610")
        self.root.minsize(700, 560)
        self.root.option_add("*Font", "Sans 10")

        self.appdir = Path(os.environ["APPDIR"]) if os.environ.get("APPDIR") else None
        self.data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        self.data_dir = self.data_home / "revoscan-linux-launcher"
        self.prefix = self.data_dir / "wineprefix"
        self.cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "revoscan-linux-launcher"
        self.installer_path = tk.StringVar()
        self.selected_adapter: GpuAdapter | None = None
        self.adapter_items: list[GpuAdapter] = []
        self.mapping_enabled = tk.BooleanVar(value=False)
        self.target_key = tk.StringVar(value="rx-7700-xt")
        self.status = tk.StringVar(value="Choose a Revo Scan Windows installer to begin.")
        self._busy = False

        self._build_ui()
        self.refresh_adapters()
        self._refresh_install_state()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Revo Scan 6 on Linux", font=("Sans", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Unofficial Wine launcher. Revopoint does not provide Linux support for this build.",
            foreground="#9a4b00",
            wraplength=720,
        ).pack(anchor="w", pady=(3, 14))

        installer_box = ttk.LabelFrame(outer, text="1 · Windows installer", padding=12)
        installer_box.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(installer_box)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.installer_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Choose .exe…", command=self.choose_installer).pack(side="left", padx=(8, 0))
        buttons = ttk.Frame(installer_box)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Find / download latest official installer", command=self.find_latest).pack(side="left")
        ttk.Button(buttons, text="Open Revopoint download page", command=lambda: webbrowser.open(SUPPORT_PAGE)).pack(side="left", padx=8)
        ttk.Label(
            installer_box,
            text="Downloads require your confirmation and come from Revopoint's HTTPS CDN. You accept the installer terms yourself.",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 0))

        gpu_box = ttk.LabelFrame(outer, text="2 · Optional GPU identity mapping (experimental)", padding=12)
        gpu_box.pack(fill="x", pady=(0, 12))
        adapter_row = ttk.Frame(gpu_box)
        adapter_row.pack(fill="x")
        ttk.Label(adapter_row, text="Detected adapter:").pack(side="left")
        self.adapter_combo = ttk.Combobox(adapter_row, state="readonly", width=56)
        self.adapter_combo.pack(side="left", fill="x", expand=True, padx=8)
        self.adapter_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_mapping_controls())
        ttk.Button(adapter_row, text="Refresh", command=self.refresh_adapters).pack(side="left")
        target_row = ttk.Frame(gpu_box)
        target_row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(
            target_row,
            text="Enable mapping (off by default)",
            variable=self.mapping_enabled,
            command=self._update_mapping_controls,
        ).pack(side="left")
        self.target_combo = ttk.Combobox(
            target_row,
            state="disabled",
            textvariable=self.target_key,
            values=tuple(AMD_TARGETS),
            width=28,
        )
        self.target_combo.pack(side="left", padx=8)
        self.target_combo.configure(values=tuple(t.name for t in AMD_TARGETS.values()))
        self._target_by_name = {t.name: t for t in AMD_TARGETS.values()}
        self.target_combo.set(AMD_TARGETS["rx-7700-xt"].name)
        ttk.Label(
            gpu_box,
            text=(
                "Mapping changes Vulkan identity only; it adds no GPU features. Intel→AMD is unverified. "
                "Do not enable unless you accept possible instability and unsupported behavior."
            ),
            foreground="#9a4b00",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 0))

        run_box = ttk.LabelFrame(outer, text="3 · Install or launch", padding=12)
        run_box.pack(fill="x", pady=(0, 12))
        run_row = ttk.Frame(run_box)
        run_row.pack(fill="x")
        self.install_button = ttk.Button(run_row, text="Run installer in Wine", command=self.run_installer)
        self.install_button.pack(side="left")
        self.launch_button = ttk.Button(run_row, text="Launch Revo Scan", command=self.launch_revoscan)
        self.launch_button.pack(side="left", padx=8)
        ttk.Button(run_row, text="Open Wine prefix folder", command=self.open_prefix).pack(side="left")
        ttk.Label(
            run_box,
            text=f"Managed prefix: {self.prefix}",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 0))

        ttk.Separator(outer).pack(fill="x", pady=(4, 8))
        ttk.Label(outer, textvariable=self.status, wraplength=720).pack(anchor="w")
        ttk.Label(
            outer,
            text="This public launcher does not include Revopoint software. It uses the host Vulkan driver; full scan/export and distro coverage must be tested.",
            foreground="#555555",
            wraplength=720,
        ).pack(anchor="w", pady=(10, 0))

    def _wine_executable(self) -> Path | None:
        if self.appdir:
            candidate = self.appdir / "usr/bin/wine64"
            if candidate.is_file():
                return candidate
        for candidate in (shutil.which("wine64"), shutil.which("wine")):
            if candidate:
                return Path(candidate)
        return None

    def _appdir_for_runtime(self) -> Path:
        return self.appdir if self.appdir else Path("/")

    def _selected_gpu(self) -> tuple[GpuAdapter | None, GpuTarget | None]:
        index = self.adapter_combo.current()
        adapter = self.adapter_items[index] if 0 <= index < len(self.adapter_items) else None
        if not self.mapping_enabled.get() or adapter is None or adapter.vendor not in {"amd", "intel"}:
            return adapter, None
        target = self._target_by_name.get(self.target_combo.get())
        return adapter, target

    def refresh_adapters(self) -> None:
        self.adapter_items = detect_adapters()
        labels = [f"{a.vendor.upper()} · {a.name} · {a.identity}" for a in self.adapter_items]
        self.adapter_combo["values"] = labels
        if labels:
            if self.adapter_combo.current() < 0:
                self.adapter_combo.current(0)
            self.status.set(f"Found {len(labels)} DRM adapter(s). Mapping remains disabled unless you enable it.")
        else:
            self.adapter_combo.set("No AMD/Intel/NVIDIA DRM adapter found")
            self.status.set("No DRM adapters found. Install/verify the host graphics driver and refresh.")
        self._update_mapping_controls()

    def _update_mapping_controls(self) -> None:
        index = self.adapter_combo.current()
        adapter = self.adapter_items[index] if 0 <= index < len(self.adapter_items) else None
        supported = adapter is not None and adapter.vendor in {"amd", "intel"}
        enabled = self.mapping_enabled.get() and supported
        self.target_combo.configure(state="readonly" if enabled else "disabled")
        if self.mapping_enabled.get() and not supported:
            self.status.set("Mapping supports AMD or Intel source adapters; choose one or leave mapping disabled.")

    def set_installer_path(self, path: str | Path) -> None:
        self.installer_path.set(str(path))
        self._refresh_install_state()

    def choose_installer(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select the official Revo Scan Windows installer",
            filetypes=[("Windows installer", "RevoScan6-*-windows-x86_64.exe"), ("Executable", "*.exe")],
        )
        if selected:
            self.set_installer_path(selected)
            self.status.set("Installer selected. Click ‘Run installer in Wine’ and complete its setup manually.")

    def find_latest(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status.set("Checking Revopoint's official support page…")
        threading.Thread(target=self._lookup_latest_worker, daemon=True).start()

    def _lookup_latest_worker(self) -> None:
        try:
            release = fetch_latest_official_installer()
            self.root.after(0, lambda: self._confirm_download(release))
        except Exception as exc:
            self.root.after(0, lambda error=exc: self._lookup_failed(error))

    def _lookup_failed(self, exc: Exception) -> None:
        self._busy = False
        self.status.set(f"Could not resolve an official direct download: {exc}")
        if messagebox.askyesno(
            "Manual download",
            "No trusted direct link was found. Open Revopoint's official download page, then select the installer here?",
            parent=self.root,
        ):
            webbrowser.open(SUPPORT_PAGE)

    def _confirm_download(self, release) -> None:
        if not messagebox.askyesno(
            "Confirm official installer download",
            f"Revopoint lists Revo Scan {release.version}.\n\nURL:\n{release.url}\n\nDownload to the launcher cache?",
            parent=self.root,
        ):
            self._busy = False
            self.status.set("Download cancelled.")
            return
        self.status.set(f"Downloading Revo Scan {release.version}…")
        threading.Thread(target=self._download_worker, args=(release,), daemon=True).start()

    def _download_worker(self, release) -> None:
        destination = self.cache_dir / Path(release.url).name
        try:
            path = download_official_installer(
                release,
                destination,
                progress=lambda done, total: self.root.after(
                    0, lambda: self.status.set(self._progress_text(done, total))
                ),
            )
            self.root.after(0, lambda: self._download_succeeded(path, release.version))
        except Exception as exc:
            self.root.after(0, lambda error=exc: self._download_failed(error))

    @staticmethod
    def _progress_text(done: int, total: int | None) -> str:
        if total:
            return f"Downloading… {done / total:.0%} ({done // (1024 * 1024)} / {total // (1024 * 1024)} MiB)"
        return f"Downloading… {done // (1024 * 1024)} MiB"

    def _download_succeeded(self, path: Path, version: str) -> None:
        self._busy = False
        self.set_installer_path(path)
        self.status.set(f"Downloaded official Revo Scan {version}. Start the installer when ready.")

    def _download_failed(self, exc: Exception) -> None:
        self._busy = False
        self.status.set(f"Installer download failed: {exc}")
        messagebox.showerror("Download failed", str(exc), parent=self.root)

    def _refresh_install_state(self) -> None:
        executable = installed_executable(self.prefix)
        selected_installer = Path(self.installer_path.get()).expanduser()
        self.launch_button.configure(state="normal" if executable.is_file() else "disabled")
        self.install_button.configure(state="normal" if selected_installer.is_file() else "disabled")

    def run_installer(self) -> None:
        installer = Path(self.installer_path.get()).expanduser()
        wine = self._wine_executable()
        if not installer.is_file():
            messagebox.showerror("Installer missing", "Choose a valid Windows installer first.", parent=self.root)
            return
        if not wine:
            messagebox.showerror("Wine missing", "This AppImage does not contain Wine and no system Wine was found.", parent=self.root)
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        env = build_revoscan_environment(self._appdir_for_runtime(), self.prefix, None, None)
        self._sanitize_prefix(env)
        env["WINELOADER"] = str(wine)
        try:
            process = subprocess.Popen([str(wine), str(installer)], env=env, cwd=str(installer.parent))
            self.status.set("Wine installer started. Complete its prompts and accept the vendor terms yourself.")
            self._poll_installer(process)
        except OSError as exc:
            messagebox.showerror("Could not start installer", str(exc), parent=self.root)

    def _poll_installer(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            self.root.after(1000, lambda: self._poll_installer(process))
            return
        self._refresh_install_state()
        self.status.set("Installer closed. Revo Scan is ready." if installed_executable(self.prefix).is_file() else "Installer closed. Finish setup or check the installer output.")

    def launch_revoscan(self) -> None:
        executable = installed_executable(self.prefix)
        wine = self._wine_executable()
        if not executable.is_file():
            messagebox.showerror("Revo Scan not installed", "Run the selected installer first.", parent=self.root)
            return
        if not wine:
            messagebox.showerror("Wine missing", "This AppImage does not contain Wine and no system Wine was found.", parent=self.root)
            return
        adapter, target = self._selected_gpu()
        try:
            env = build_revoscan_environment(
                self._appdir_for_runtime(), self.prefix, adapter, target
            )
            self._sanitize_prefix(env)
            env["WINELOADER"] = str(wine)
            subprocess.Popen([str(wine), str(executable)], env=env, cwd=str(executable.parent))
            if target:
                self.status.set(
                    f"Started Revo Scan. Mapping {adapter.name if adapter else 'selected GPU'} to {target.name}; verify GPU use in the app."
                )
            else:
                self.status.set("Started Revo Scan without GPU identity mapping.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not launch Revo Scan", str(exc), parent=self.root)

    def _sanitize_prefix(self, env: dict[str, str]) -> None:
        """Strip Wine's Bluetooth driver from the prefix before wine runs."""
        removed = sanitize_bluetooth(self.prefix)
        if removed:
            self.status.set(
                "Removed Wine Bluetooth driver from the prefix: " + ", ".join(removed)
            )

    def open_prefix(self) -> None:
        self.prefix.mkdir(parents=True, exist_ok=True)
        opener = shutil.which("xdg-open")
        command = [opener, str(self.prefix)] if opener else None
        if command is None:
            gio = shutil.which("gio")
            command = [gio, "open", str(self.prefix)] if gio else None
        if command is None:
            self.status.set(f"No desktop opener found. Wine prefix: {self.prefix}")
            return
        try:
            subprocess.Popen(command, env=desktop_opener_environment())
            self.status.set(f"Opening Wine prefix folder: {self.prefix}")
        except OSError as exc:
            self.status.set(f"Could not open Wine prefix folder: {exc}. Path: {self.prefix}")


def main() -> None:
    root = tk.Tk()
    Launcher(root)
    root.mainloop()
