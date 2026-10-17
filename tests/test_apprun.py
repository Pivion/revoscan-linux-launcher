import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AppRunEnvironmentTests(unittest.TestCase):
    def test_apprun_preserves_the_original_host_library_path(self):
        with tempfile.TemporaryDirectory() as temp:
            appdir = Path(temp)
            launcher = appdir / "usr/bin/revoscan-launcher"
            launcher.parent.mkdir(parents=True)
            launcher.write_text(
                '#!/bin/sh\nprintf "%s\\n%s\\n" "$REVOSCAN_HOST_LD_LIBRARY_PATH" "$LD_LIBRARY_PATH"\n',
                encoding="utf-8",
            )
            launcher.chmod(0o755)
            env = {
                "APPDIR": str(appdir),
                "PATH": "/usr/bin:/bin",
                "LD_LIBRARY_PATH": "/opt/host-vulkan/lib:/opt/custom/lib",
            }
            result = subprocess.run(
                ["bash", str(ROOT / "packaging/AppRun")],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "/opt/host-vulkan/lib:/opt/custom/lib")
        self.assertIn(str(appdir / "usr/share/vulkan/explicit_layer.d"), lines[1])
