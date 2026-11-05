import json
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from revoscan_launcher.gpu import AMD_TARGETS, GpuAdapter
from revoscan_launcher.runtime import (
    LAYER_NAME,
    build_revoscan_environment,
    clear_wine_gpu_override,
    mapping_layer_dir,
    set_wine_gpu_override,
)


ROOT = Path(__file__).resolve().parents[1]
LAYER_SOURCE = ROOT / "src/vulkan_layer"


def stage_layer(appdir: Path) -> Path:
    layer_dir = appdir / "usr/share/vulkan/explicit_layer.d"
    layer_dir.mkdir(parents=True)
    (layer_dir / f"{LAYER_NAME}.json").write_text(
        (LAYER_SOURCE / f"{LAYER_NAME}.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (layer_dir / "librevoscan_gpu_map.so").write_bytes(b"test fixture")
    return layer_dir


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
        with tempfile.TemporaryDirectory() as temp:
            appdir = Path(temp) / "app"
            layer_dir = stage_layer(appdir)
            env = build_revoscan_environment(
                appdir=appdir,
                prefix=Path("/home/test/prefix"),
                adapter=adapter,
                target=AMD_TARGETS["rx-7700-xt"],
                base_env={"PATH": "/usr/bin"},
            )
            self.assertEqual(env["VK_INSTANCE_LAYERS"], LAYER_NAME)
            self.assertEqual(env["REVOSCAN_MAP_SOURCE_DEVICE"], "1900")
            self.assertEqual(env["VK_LAYER_PATH"], str(layer_dir))
            self.assertIn("/usr/bin", env["PATH"])

    def test_mapping_without_layer_files_does_not_claim_a_layer_path(self):
        """An AppImage/source tree without the layer must not spoof a layer path.

        A VK_LAYER_PATH pointing at a missing directory makes the Vulkan loader
        search only that path, so the mapping silently never applies.
        """
        adapter = GpuAdapter.from_pci("0x8086", "0xfd80", "Intel Graphics")
        with tempfile.TemporaryDirectory() as temp:
            env = build_revoscan_environment(
                appdir=Path(temp),
                prefix=Path(temp) / "prefix",
                adapter=adapter,
                target=AMD_TARGETS["rx-7700-xt"],
                base_env={},
            )
        self.assertNotIn("VK_LAYER_PATH", env)
        self.assertNotIn("VK_INSTANCE_LAYERS", env)
        self.assertFalse(any(key.startswith("REVOSCAN_MAP_") for key in env))

    def test_mapping_layer_dir_requires_both_manifest_and_library(self):
        with tempfile.TemporaryDirectory() as temp:
            appdir = Path(temp)
            manifest = appdir / "usr/share/vulkan/explicit_layer.d" / f"{LAYER_NAME}.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
            self.assertIsNone(mapping_layer_dir(appdir))
            (manifest.parent / "librevoscan_gpu_map.so").write_bytes(b"so")
            self.assertEqual(mapping_layer_dir(appdir), manifest.parent)

    def test_layer_manifest_uses_manifest_relative_library_path(self):
        """A bare library name relies on LD_LIBRARY_PATH; './name' is spec-correct."""
        manifest = json.loads(
            (LAYER_SOURCE / f"{LAYER_NAME}.json").read_text(encoding="utf-8")
        )
        entry = manifest.get("layer") or manifest["layers"][0]
        self.assertTrue(entry["library_path"].startswith("./"), entry["library_path"])
        self.assertEqual(entry["name"], LAYER_NAME)


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


class WineGpuOverrideTests(unittest.TestCase):
    def test_mapping_switches_wined3d_to_the_vulkan_renderer(self):
        calls = []

        def fake_reg(wine, env, args):
            calls.append(args)
            return True, "reg: The operation completed successfully"

        with patch("revoscan_launcher.runtime._wine_reg", side_effect=fake_reg):
            report = set_wine_gpu_override(
                Path("/prefix"), Path("/wine"), {}, AMD_TARGETS["rx-7700-xt"]
            )
        self.assertTrue(any("renderer" in call and "vulkan" in call for call in calls), calls)
        self.assertIn("renderer=vulkan: ok", report)
        # The legacy identity keys are not honoured by this Wine build.
        self.assertFalse(any("VideoPciVendorID" in call for call in calls))

    def test_clearing_removes_the_renderer_selection(self):
        calls = []

        def fake_reg(wine, env, args):
            calls.append(args)
            return True, "ok"

        with patch("revoscan_launcher.runtime._wine_reg", side_effect=fake_reg):
            report = clear_wine_gpu_override(Path("/prefix"), Path("/wine"), {})
        deleted = [call[call.index("/v") + 1] for call in calls if "delete" in call]
        self.assertIn("renderer", deleted)
        self.assertTrue(any("renderer: cleared" in item for item in report))


if __name__ == "__main__":
    unittest.main()
