import tempfile
import textwrap
import unittest
from pathlib import Path

from revoscan_launcher.runtime import sanitize_bluetooth


SYSTEM_REG = textwrap.dedent(
    """\
    [System\\CurrentControlSet\\Services\\winebus]
    "Start"="3"

    [System\\CurrentControlSet\\Services\\winebth]
    "Description"="Wine Bluetooth bus driver"
    "Start"="3"

    [System\\CurrentControlSet\\Enum\\winebth\\RADIO\\1&5119afcf&0&_org_bluez_hci0]
    "ClassGUID"="{92383B0E-F90E-4AC9-8D44-8C2D0D0EBDA2}"
    "FriendlyName"="Wine Bluetooth Radio"

    [Software\\Wine\\X11 Driver]
    "Managed"="Y"
    """
)


class BluetoothSanitizerTests(unittest.TestCase):
    def test_removes_staged_driver_files_and_registry_sections(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            staged = prefix / "drive_c/windows/system32/drivers/winebth.sys"
            staged.parent.mkdir(parents=True)
            staged.write_text("driver")
            syswow = prefix / "drive_c/windows/syswow64/drivers/winebth.sys"
            syswow.parent.mkdir(parents=True)
            syswow.write_text("driver")
            reg = prefix / "system.reg"
            reg.write_text(SYSTEM_REG, encoding="utf-8")

            removed = sanitize_bluetooth(prefix)

            self.assertFalse(staged.exists())
            self.assertFalse(syswow.exists())
            content = reg.read_text(encoding="utf-8")
            self.assertNotIn("winebth", content)
            self.assertIn("[System\\CurrentControlSet\\Services\\winebus]", content)
            self.assertIn("[Software\\Wine\\X11 Driver]", content)
            self.assertIn('"Managed"="Y"', content)
            self.assertTrue(any("winebth" in item for item in removed))

    def test_is_a_noop_on_clean_or_missing_prefixes(self):
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp)
            self.assertEqual(sanitize_bluetooth(prefix), [])
        self.assertEqual(sanitize_bluetooth(Path(temp) / "missing"), [])

    def test_build_script_strips_winebth_from_bundled_wine(self):
        script = (
            Path(__file__).resolve().parents[1] / "scripts/build-appimage-in-container.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("winebth.sys", script)
        self.assertIn("winebth.so", script)
        for relative in (
            "x86_64-windows/winebth.sys",
            "i386-windows/winebth.sys",
            "x86_64-unix/winebth.so",
            "i386-unix/winebth.so",
        ):
            self.assertIn(relative, script)


if __name__ == "__main__":
    unittest.main()
