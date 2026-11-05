"""Tk launcher UI; business logic lives in installer/gpu/runtime modules."""

from __future__ import annotations

import os
from pathlib import Path
import io
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
from .network import (
    ensure_firewall_allows,
    firewall_report,
    parse_subnets,
    scanner_subnets,
)
from .runtime import (
    build_revoscan_environment,
    clear_wine_gpu_override,
    installed_executable,
    mapping_layer_dir,
    sanitize_bluetooth,
    set_wine_gpu_override,
)


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
        self.root.title("Revo Scan on Linux")
        self.root.geometry("780x720")
        self.root.minsize(700, 660)
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
        self.target_key = tk.StringVar(value="intel-b580")
        self.status = tk.StringVar(value="Choose the Revo Scan installer to begin.")
        self._busy = False

        self._build_ui()
        self.refresh_adapters()
        # The firewall probe runs only when the user asks for it: firewalld
        # queries go through polkit and can prompt for a password, which must
        # never happen as a side effect of opening the launcher.
        self._refresh_install_state()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Revo Scan 6 on Linux", font=("Sans", 18, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Unofficial launcher — not supported by Revopoint.",
            foreground="#9a4b00",
            wraplength=720,
        ).pack(anchor="w", pady=(3, 14))

        installer_box = ttk.LabelFrame(outer, text="1 · Installer", padding=12)
        installer_box.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(installer_box)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.installer_path).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Choose installer…", command=self.choose_installer).pack(side="left", padx=(8, 0))
        buttons = ttk.Frame(installer_box)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Download latest from Revopoint", command=self.find_latest).pack(side="left")
        ttk.Button(buttons, text="Revopoint download page", command=lambda: webbrowser.open(SUPPORT_PAGE)).pack(side="left", padx=8)
        ttk.Label(
            installer_box,
            text="Downloads come from Revopoint and ask for your confirmation. You accept their terms.",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 0))

        scan_box = ttk.LabelFrame(outer, text="2 · Scanner", padding=12)
        scan_box.pack(fill="x", pady=(0, 12))
        ttk.Label(
            scan_box,
            text=(
                "Connect your spare Wi-Fi adapter to the scanner's access point in your desktop's "
                "network settings, then allow it through the firewall."
            ),
            wraplength=700,
        ).pack(anchor="w")
        firewall_row = ttk.Frame(scan_box)
        firewall_row.pack(fill="x", pady=(8, 0))
        ttk.Label(firewall_row, text="Scanner network:").pack(side="left")
        self.scanner_subnet = tk.StringVar()
        ttk.Entry(firewall_row, textvariable=self.scanner_subnet, width=24).pack(side="left", padx=8)
        self.firewall_button = ttk.Button(
            firewall_row, text="Allow scanner", command=self.allow_firewall
        )
        self.firewall_button.pack(side="left")
        ttk.Button(
            firewall_row, text="Check status", command=self.refresh_firewall_status
        ).pack(side="left", padx=8)
        self.firewall_status = tk.StringVar(
            value=(
                "Click Check status to see whether the firewall lets the scanner through."
            )
        )
        ttk.Label(scan_box, textvariable=self.firewall_status, wraplength=700).pack(
            anchor="w", pady=(8, 0)
        )

        gpu_box = ttk.LabelFrame(outer, text="3 · GPU (optional, experimental)", padding=12)
        gpu_box.pack(fill="x", pady=(0, 12))
        adapter_row = ttk.Frame(gpu_box)
        adapter_row.pack(fill="x")
        ttk.Label(adapter_row, text="Detected GPU:").pack(side="left")
        self.adapter_combo = ttk.Combobox(adapter_row, state="readonly", width=56)
        self.adapter_combo.pack(side="left", fill="x", expand=True, padx=8)
        self.adapter_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_mapping_controls())
        ttk.Button(adapter_row, text="Refresh", command=self.refresh_adapters).pack(side="left")
        ttk.Button(adapter_row, text="Test", command=self.verify_mapping).pack(
            side="left", padx=(8, 0)
        )
        target_row = ttk.Frame(gpu_box)
        target_row.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(
            target_row,
            text="Report GPU as:",
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
        self.target_combo.set(AMD_TARGETS["intel-b580"].name)
        ttk.Label(
            gpu_box,
            text=(
                "Changes what Revo Scan sees, not what your GPU can do. "
                "Use it only if Revo Scan won't use your GPU."
            ),
            foreground="#9a4b00",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 0))
        self.mapping_status = tk.StringVar(value="")
        ttk.Label(gpu_box, textvariable=self.mapping_status, foreground="#555555", wraplength=700).pack(
            anchor="w", pady=(6, 0)
        )

        run_box = ttk.LabelFrame(outer, text="4 · Revo Scan", padding=12)
        run_box.pack(fill="x", pady=(0, 12))
        run_row = ttk.Frame(run_box)
        run_row.pack(fill="x")
        self.install_button = ttk.Button(run_row, text="Install Revo Scan", command=self.run_installer)
        self.install_button.pack(side="left")
        self.launch_button = ttk.Button(run_row, text="Launch Revo Scan", command=self.launch_revoscan)
        self.launch_button.pack(side="left", padx=8)
        ttk.Button(run_row, text="Open data folder", command=self.open_prefix).pack(side="left")
        ttk.Label(
            run_box,
            text=f"Data folder: {self.prefix}",
            wraplength=700,
        ).pack(anchor="w", pady=(8, 0))

        ttk.Separator(outer).pack(fill="x", pady=(4, 8))
        ttk.Label(outer, textvariable=self.status, wraplength=720).pack(anchor="w")
        ttk.Label(
            outer,
            text="Revopoint software is not bundled. Scan quality and Linux support are still being tested.",
            foreground="#555555",
            wraplength=720,
        ).pack(anchor="w", pady=(10, 0))

    def _runtime_appdir(self) -> Path | None:
        """AppImage dir when running from the AppImage, else the extracted
        per-user runtime (~/.local/share/revoscan-linux-launcher/appdir)."""
        if self.appdir and (self.appdir / "usr/bin/wine64").is_file():
            return self.appdir
        extracted = self.data_dir / "appdir"
        if (extracted / "usr/bin/wine64").is_file():
            return extracted
        return None

    def _wine_executable(self) -> Path | None:
        appdir = self._runtime_appdir()
        if appdir:
            candidate = appdir / "usr/bin/wine64"
            if candidate.is_file():
                return candidate
        for candidate in (shutil.which("wine64"), shutil.which("wine")):
            if candidate:
                return Path(candidate)
        return None

    def _appdir_for_runtime(self) -> Path:
        return self._runtime_appdir() or Path("/")

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
            self.status.set(f"Found {len(labels)} GPU(s).")
        else:
            self.adapter_combo.set("No AMD/Intel/NVIDIA DRM adapter found")
            self.status.set("No GPU found. Check your graphics driver, then refresh.")
        self._update_mapping_controls()

    def _update_mapping_controls(self) -> None:
        index = self.adapter_combo.current()
        adapter = self.adapter_items[index] if 0 <= index < len(self.adapter_items) else None
        supported = adapter is not None and adapter.vendor in {"amd", "intel"}
        enabled = self.mapping_enabled.get() and supported
        self.target_combo.configure(state="readonly" if enabled else "disabled")
        if self.mapping_enabled.get() and not supported:
            self.status.set(
                "GPU mapping works with AMD and Intel GPUs."
            )
        self._update_mapping_status()

    def _update_mapping_status(self) -> None:
        if not self.mapping_enabled.get():
            self.mapping_status.set("")
            return
        layer_dir = mapping_layer_dir(self._appdir_for_runtime())
        if layer_dir is None:
            self.mapping_status.set(
                "GPU mapping isn't available in this build. Revo Scan will start without it."
            )
        else:
            self.mapping_status.set("Ready.")

    def verify_mapping(self) -> None:
        adapter, target = self._selected_gpu()
        if target is None or adapter is None:
            self.mapping_status.set("Turn on GPU mapping and pick a target first.")
            return
        self.mapping_status.set("Testing…")
        threading.Thread(
            target=self._verify_mapping_worker, args=(adapter, target), daemon=True
        ).start()

    def _verify_mapping_worker(self, adapter: GpuAdapter, target: GpuTarget) -> None:
        from .entrypoint import check_vulkan_identity

        buffer = io.StringIO()
        try:
            check_vulkan_identity(buffer, source=adapter, target=target)
            text = buffer.getvalue().strip()
        except Exception as exc:  # pragma: no cover - defensive
            text = f"Mapping check failed: {exc}"
        self.root.after(0, lambda: self.mapping_status.set(text[-700:] or "No output."))

    def _detected_scanner_subnets(self) -> list[str]:
        try:
            return [link.cidr for link in scanner_subnets()]
        except (OSError, subprocess.SubprocessError):
            return []

    def refresh_firewall_status(self) -> None:
        threading.Thread(target=self._firewall_status_worker, daemon=True).start()

    def _firewall_status_worker(self) -> None:
        subnets = self._detected_scanner_subnets()
        try:
            report = firewall_report(subnets[:1])
        except Exception as exc:
            self.root.after(
                0, lambda error=exc: self.firewall_status.set(f"Firewall check failed: {error}")
            )
            return
        self.root.after(0, lambda: self._show_firewall_report(subnets, report))

    def _show_firewall_report(self, subnets: list[str], report) -> None:
        if not self.scanner_subnet.get() and subnets:
            self.scanner_subnet.set(subnets[0])
        self.firewall_status.set(report.describe())

    def allow_firewall(self) -> None:
        text = self.scanner_subnet.get().strip()
        if not text:
            # Cheap, password-free lookup: only `ip`, never firewalld.
            detected = self._detected_scanner_subnets()
            if detected:
                self.scanner_subnet.set(detected[0])
                text = detected[0]
        try:
            targets = parse_subnets(text)
        except ValueError as exc:
            self.firewall_status.set(f"That isn't a valid address: {exc}")
            return
        if not targets:
            self.firewall_status.set(
                "Enter the scanner's network first."
            )
            return
        self.firewall_button.configure(state="disabled")
        self.firewall_status.set("Allowing the scanner…")
        threading.Thread(target=self._firewall_allow_worker, args=(targets,), daemon=True).start()

    def _firewall_allow_worker(self, targets: list[str]) -> None:
        messages: list[str] = []
        for target in targets:
            try:
                ok, message = ensure_firewall_allows(target)
            except Exception as exc:  # pragma: no cover - defensive
                ok, message = False, f"{target}: {exc}"
            messages.append(message)
            if not ok:
                break
        self.root.after(0, lambda: self._firewall_allow_done(messages))

    def _firewall_allow_done(self, messages: list[str]) -> None:
        self.firewall_button.configure(state="normal")
        self.firewall_status.set(" ".join(messages))

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
            self.status.set("Installer selected. Click Install Revo Scan.")

    def find_latest(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status.set("Looking for the latest installer…")
        threading.Thread(target=self._lookup_latest_worker, daemon=True).start()

    def _lookup_latest_worker(self) -> None:
        try:
            release = fetch_latest_official_installer()
            self.root.after(0, lambda: self._confirm_download(release))
        except Exception as exc:
            self.root.after(0, lambda error=exc: self._lookup_failed(error))

    def _lookup_failed(self, exc: Exception) -> None:
        self._busy = False
        self.status.set(f"Couldn't find a download link: {exc}")
        if messagebox.askyesno(
            "Manual download",
            "No download link found. Open Revopoint's download page in your browser?",
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
        self.status.set(f"Downloaded Revo Scan {version}.")

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
            messagebox.showerror("No installer", "Choose the Revo Scan installer first.", parent=self.root)
            return
        if not wine:
            messagebox.showerror("Wine missing", "Wine is missing from this build.", parent=self.root)
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        env = build_revoscan_environment(self._appdir_for_runtime(), self.prefix, None, None)
        self._sanitize_prefix(env)
        env["WINELOADER"] = str(wine)
        try:
            process = subprocess.Popen([str(wine), str(installer)], env=env, cwd=str(installer.parent))
            self.status.set("Follow the installer's prompts.")
            self._poll_installer(process)
        except OSError as exc:
            messagebox.showerror("Could not start installer", str(exc), parent=self.root)

    def _poll_installer(self, process: subprocess.Popen) -> None:
        if process.poll() is None:
            self.root.after(1000, lambda: self._poll_installer(process))
            return
        self._refresh_install_state()
        self.status.set("Installation finished." if installed_executable(self.prefix).is_file() else "Installer closed. Check its output if Revo Scan didn't install.")

    def launch_revoscan(self) -> None:
        executable = installed_executable(self.prefix)
        wine = self._wine_executable()
        if not executable.is_file():
            messagebox.showerror("Revo Scan not installed", "Install Revo Scan first.", parent=self.root)
            return
        if not wine:
            messagebox.showerror("Wine missing", "Wine is missing from this build.", parent=self.root)
            return
        adapter, target = self._selected_gpu()
        if target is not None and mapping_layer_dir(self._appdir_for_runtime()) is None:
            target = None
            self.mapping_status.set(
                "GPU mapping isn't available here — starting without it."
            )
        try:
            env = build_revoscan_environment(
                self._appdir_for_runtime(), self.prefix, adapter, target
            )
            self._sanitize_prefix(env)
            env["WINELOADER"] = str(wine)
            if target:
                # Revo Scan reads its GPU list from DXGI; the wined3d renderer
                # switch makes that read the layer's mapped Vulkan identity.
                set_wine_gpu_override(self.prefix, wine, env, target)
            else:
                clear_wine_gpu_override(self.prefix, wine, env)
            subprocess.Popen([str(wine), str(executable)], env=env, cwd=str(executable.parent))
            if target:
                self.status.set(
                    f"Revo Scan started. GPU reported as {target.name}."
                )
            else:
                self.status.set("Revo Scan started.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not launch Revo Scan", str(exc), parent=self.root)

    def _sanitize_prefix(self, env: dict[str, str]) -> None:
        """Strip Wine's Bluetooth driver from the prefix before wine runs."""
        removed = sanitize_bluetooth(self.prefix)
        if removed:
            self.status.set(
                "Adjusted the Wine setup for this launch."
            )

    def open_prefix(self) -> None:
        self.prefix.mkdir(parents=True, exist_ok=True)
        opener = shutil.which("xdg-open")
        command = [opener, str(self.prefix)] if opener else None
        if command is None:
            gio = shutil.which("gio")
            command = [gio, "open", str(self.prefix)] if gio else None
        if command is None:
            self.status.set(f"No file manager found. Data folder: {self.prefix}")
            return
        try:
            subprocess.Popen(command, env=desktop_opener_environment())
            self.status.set(f"Opening {self.prefix}")
        except OSError as exc:
            self.status.set(f"Couldn't open the data folder: {exc}")


def main() -> None:
    root = tk.Tk()
    Launcher(root)
    root.mainloop()
