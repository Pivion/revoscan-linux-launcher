import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from revoscan_launcher.gui import Launcher
from revoscan_launcher.network import FirewallReport


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeButton:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        self.state = kwargs.get("state")


class InstallerButtonStateTests(unittest.TestCase):
    def test_selecting_a_valid_installer_enables_run_installer_button(self):
        with tempfile.TemporaryDirectory() as temp:
            installer = Path(temp) / "RevoScan6-6.4.1.1088-windows-x86_64.exe"
            installer.write_bytes(b"test fixture")
            launcher = Launcher.__new__(Launcher)
            launcher.installer_path = FakeVar()
            launcher.prefix = Path(temp) / "prefix"
            launcher.install_button = FakeButton()
            launcher.launch_button = FakeButton()
            launcher.set_installer_path(installer)
            self.assertEqual(launcher.install_button.state, "normal")

    def test_nonexistent_installer_keeps_run_button_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            launcher = Launcher.__new__(Launcher)
            launcher.installer_path = FakeVar()
            launcher.prefix = Path(temp) / "prefix"
            launcher.install_button = FakeButton()
            launcher.launch_button = FakeButton()
            launcher.set_installer_path(Path(temp) / "missing.exe")
            self.assertEqual(launcher.install_button.state, "disabled")

    def test_open_prefix_removes_appimage_library_paths_for_desktop_opener(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / "wineprefix"
            launcher = Launcher.__new__(Launcher)
            launcher.prefix = prefix
            launcher.__dict__["status"] = FakeVar()
            polluted = {
                "PATH": "/usr/bin",
                "HOME": temp,
                "LD_LIBRARY_PATH": "/tmp/_MEI123:/tmp/.mount_Revo/usr/lib",
                "LD_PRELOAD": "/tmp/_MEI123/libssl.so.3",
                "DISPLAY": ":0",
                "WAYLAND_DISPLAY": "wayland-0",
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            }
            with patch.dict(os.environ, polluted, clear=True), patch(
                "revoscan_launcher.gui.shutil.which", return_value="/usr/bin/xdg-open"
            ), patch("revoscan_launcher.gui.subprocess.Popen") as popen:
                launcher.open_prefix()
            args, kwargs = popen.call_args
            self.assertEqual(args[0], ["/usr/bin/xdg-open", str(prefix)])
            self.assertNotIn("LD_LIBRARY_PATH", kwargs["env"])
            self.assertNotIn("LD_PRELOAD", kwargs["env"])
            self.assertEqual(kwargs["env"]["DISPLAY"], ":0")
            self.assertEqual(kwargs["env"]["DBUS_SESSION_BUS_ADDRESS"], polluted["DBUS_SESSION_BUS_ADDRESS"])


class FakeRoot:
    def after(self, _delay, callback):
        callback()


class FirewallUiTests(unittest.TestCase):
    def make_launcher(self):
        launcher = Launcher.__new__(Launcher)
        launcher.root = FakeRoot()
        launcher.scanner_subnet = FakeVar("")
        launcher.firewall_status = FakeVar()
        launcher.firewall_button = FakeButton()
        return launcher

    def test_report_prefills_detected_subnet_and_describes_state(self):
        launcher = self.make_launcher()
        report = FirewallReport(state="running", missing=("192.168.179.0/24",))
        launcher._show_firewall_report(["192.168.179.0/24"], report)
        self.assertEqual(launcher.scanner_subnet.get(), "192.168.179.0/24")
        self.assertIn("Allow scanner", launcher.firewall_status.get())

    def test_report_keeps_a_manually_entered_subnet(self):
        launcher = self.make_launcher()
        launcher.scanner_subnet.set("10.0.0.0/24")
        launcher._show_firewall_report(
            ["192.168.179.0/24"], FirewallReport(state="running")
        )
        self.assertEqual(launcher.scanner_subnet.get(), "10.0.0.0/24")

    def test_allow_worker_applies_each_subnet_and_reports_messages(self):
        launcher = self.make_launcher()
        calls = []

        def fake_allow(address):
            calls.append(address)
            return True, f"firewalld now allows {address} (rule persisted)."

        with patch("revoscan_launcher.gui.ensure_firewall_allows", side_effect=fake_allow):
            launcher._firewall_allow_worker(["192.168.179.0/24", "192.168.8.0/24"])
        self.assertEqual(calls, ["192.168.179.0/24", "192.168.8.0/24"])
        self.assertIn("192.168.8.0/24", launcher.firewall_status.get())
        self.assertEqual(launcher.firewall_button.state, "normal")

    def test_allow_worker_stops_after_elevation_failure(self):
        launcher = self.make_launcher()
        calls = []

        def fake_allow(address):
            calls.append(address)
            return False, "Elevation required — run: sudo firewall-cmd …"

        with patch("revoscan_launcher.gui.ensure_firewall_allows", side_effect=fake_allow):
            launcher._firewall_allow_worker(["192.168.179.0/24", "192.168.8.0/24"])
        self.assertEqual(calls, ["192.168.179.0/24"])
        self.assertIn("Elevation required", launcher.firewall_status.get())

    def test_allow_button_rejects_invalid_subnet_without_running_anything(self):
        launcher = self.make_launcher()
        launcher.scanner_subnet.set("999.1.1.1")
        with patch("revoscan_launcher.gui.threading.Thread") as thread:
            launcher.allow_firewall()
        thread.assert_not_called()
        self.assertIn("valid address", launcher.firewall_status.get())

    def test_allow_button_asks_for_a_subnet_when_empty(self):
        launcher = self.make_launcher()
        with patch.object(Launcher, "_detected_scanner_subnets", return_value=[]), patch(
            "revoscan_launcher.gui.threading.Thread"
        ) as thread:
            launcher.allow_firewall()
        thread.assert_not_called()
        self.assertIn("Enter the scanner", launcher.firewall_status.get())

    def test_allow_button_auto_detects_a_subnet_when_the_field_is_empty(self):
        launcher = self.make_launcher()
        created = []

        class FakeThread:
            def __init__(self, target=None, args=(), daemon=None):
                created.append((target, args))

            def start(self):
                pass

        with patch.object(
            Launcher, "_detected_scanner_subnets", return_value=["192.168.179.0/24"]
        ), patch("revoscan_launcher.gui.threading.Thread", FakeThread):
            launcher.allow_firewall()
        self.assertEqual(launcher.scanner_subnet.get(), "192.168.179.0/24")
        self.assertEqual(created[0][1], (["192.168.179.0/24"],))
        self.assertEqual(launcher.firewall_button.state, "disabled")


class MappingStatusTests(unittest.TestCase):
    def test_missing_layer_is_reported_instead_of_claiming_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            launcher = Launcher.__new__(Launcher)
            launcher.mapping_enabled = FakeVar(True)
            launcher.mapping_status = FakeVar()
            with patch.object(Launcher, "_appdir_for_runtime", return_value=Path(temp)):
                launcher._update_mapping_status()
            self.assertIn("isn't available", launcher.mapping_status.get())

    def test_ready_layer_path_is_shown(self):
        with tempfile.TemporaryDirectory() as temp:
            layer_dir = Path(temp) / "usr/share/vulkan/explicit_layer.d"
            layer_dir.mkdir(parents=True)
            (layer_dir / "VK_LAYER_REVOSCAN_LINUX_GPU_MAP.json").write_text("{}", encoding="utf-8")
            (layer_dir / "librevoscan_gpu_map.so").write_bytes(b"so")
            launcher = Launcher.__new__(Launcher)
            launcher.mapping_enabled = FakeVar(True)
            launcher.mapping_status = FakeVar()
            with patch.object(Launcher, "_appdir_for_runtime", return_value=Path(temp)):
                launcher._update_mapping_status()
            self.assertEqual(launcher.mapping_status.get(), "Ready.")


if __name__ == "__main__":
    unittest.main()
