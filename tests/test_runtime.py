import tempfile
import unittest
from pathlib import Path

from revoscan_launcher.gpu import AMD_TARGETS, GpuAdapter
from revoscan_launcher.runtime import build_revoscan_environment


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_no_mapping_never_enables_spoof_layer(self):
        env = build_revoscan_environment(
            appdir=Path("/opt/app"),
            prefix=Path("/home/test/.local/share/revoscan/prefix"),
            adapter=None,
            target=None,
            base_env={},
        )
        self.assertNotIn("VK_INSTANCE_LAYERS", env)
        self.assertEqual(env["WINEPREFIX"], "/home/test/.local/share/revoscan/prefix")
        self.assertEqual(env["WINEARCH"], "win64")

    def test_mapping_sets_layer_and_selected_adapter(self):
        adapter = GpuAdapter.from_pci("0x1002", "0x1900", "AMD Radeon 780M")
        env = build_revoscan_environment(
            appdir=Path("/opt/app"),
            prefix=Path("/home/test/prefix"),
            adapter=adapter,
            target=AMD_TARGETS["rx-7700-xt"],
            base_env={"PATH": "/usr/bin"},
        )
        self.assertEqual(env["VK_INSTANCE_LAYERS"], "VK_LAYER_REVOSCAN_LINUX_GPU_MAP")
        self.assertEqual(env["REVOSCAN_MAP_SOURCE_DEVICE"], "1900")
        self.assertTrue(env["VK_LAYER_PATH"].endswith("explicit_layer.d"))
        self.assertIn("/usr/bin", env["PATH"])

    def test_wine_child_drops_pyinstaller_library_path_and_keeps_host_path(self):
        with tempfile.TemporaryDirectory() as temp:
            appdir = Path(temp) / "app"
            wine_lib = appdir / "opt/wine-staging/lib/wine"
            wine_lib.mkdir(parents=True)
            env = build_revoscan_environment(
                appdir=appdir,
                prefix=Path(temp) / "prefix",
                adapter=None,
                target=None,
                base_env={
                    "LD_LIBRARY_PATH": "/tmp/_MEI000abc:/tmp/.mount_Revo/usr/lib",
                    "REVOSCAN_HOST_LD_LIBRARY_PATH": "/opt/host-vulkan/lib",
                },
            )
            self.assertNotIn("_MEI000abc", env["LD_LIBRARY_PATH"])
            self.assertNotIn("/tmp/.mount_Revo/usr/lib", env["LD_LIBRARY_PATH"])
            self.assertIn("/opt/host-vulkan/lib", env["LD_LIBRARY_PATH"])
            self.assertNotIn("REVOSCAN_HOST_LD_LIBRARY_PATH", env)

    def test_ubuntu_staged_wine_root_is_selected_when_present(self):
        with tempfile.TemporaryDirectory() as temp:
            appdir = Path(temp)
            wine_lib = appdir / "opt/wine-staging/lib/wine"
            wine_lib.mkdir(parents=True)
            env = build_revoscan_environment(
                appdir=appdir,
                prefix=appdir / "prefix",
                adapter=None,
                target=None,
                base_env={},
            )
            self.assertIn(str(wine_lib), env["WINEDLLPATH"])
            self.assertIn(str(wine_lib / "x86_64-unix"), env["LD_LIBRARY_PATH"])


if __name__ == "__main__":
    unittest.main()
