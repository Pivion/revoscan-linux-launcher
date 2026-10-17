import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from revoscan_launcher.installer import (
    InstallerError,
    OfficialInstaller,
    download_official_installer,
)


class DownloadSafetyTests(unittest.TestCase):
    def test_version_must_match_the_official_filename_before_network_access(self):
        release = OfficialInstaller(
            "9.9.9",
            "https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.3.2.1028-windows-x86_64.exe",
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "installer.exe"
            with patch(
                "revoscan_launcher.installer.urlopen",
                side_effect=AssertionError("network must not be reached"),
            ):
                with self.assertRaises(InstallerError):
                    download_official_installer(release, destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
