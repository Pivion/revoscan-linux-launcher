import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from revoscan_launcher.gui import Launcher


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


if __name__ == "__main__":
    unittest.main()
