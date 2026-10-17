from io import StringIO
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from revoscan_launcher.entrypoint import run
from revoscan_launcher.installer import OfficialInstaller


class EntrypointDiagnosticsTests(unittest.TestCase):
    def test_latest_installer_diagnostic_prints_without_starting_gui(self):
        output = StringIO()
        release = OfficialInstaller(
            "6.4.1.1088",
            "https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.4.1.1088-windows-x86_64.exe",
        )
        with patch(
            "revoscan_launcher.installer.fetch_latest_official_installer",
            return_value=release,
        ):
            result = run(argv=["--check-latest-installer"], stdout=output)
        self.assertEqual(result, 0)
        self.assertIn("6.4.1.1088", output.getvalue())
        self.assertIn(release.url, output.getvalue())

    def test_bundled_wine_check_excludes_pyinstaller_temp_libraries(self):
        with tempfile.TemporaryDirectory() as temp:
            appdir = Path(temp) / "app"
            wine = appdir / "usr/bin/wine64"
            wine.parent.mkdir(parents=True)
            wine.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$LD_LIBRARY_PATH"\nprintf "wine-test\\n"\n',
                encoding="utf-8",
            )
            wine.chmod(0o755)
            output = StringIO()
            with patch.dict(
                os.environ,
                {
                    "APPDIR": str(appdir),
                    "LD_LIBRARY_PATH": "/tmp/_MEIabc:/tmp/.mount/app/lib",
                    "REVOSCAN_HOST_LD_LIBRARY_PATH": "/opt/host-vulkan/lib",
                    "PATH": "/usr/bin:/bin",
                },
                clear=True,
            ):
                result = run(argv=["--check-wine"], stdout=output)
        self.assertEqual(result, 0)
        self.assertNotIn("_MEIabc", output.getvalue())
        self.assertIn("/opt/host-vulkan/lib", output.getvalue())
        self.assertIn("wine-test", output.getvalue())


if __name__ == "__main__":
    unittest.main()
