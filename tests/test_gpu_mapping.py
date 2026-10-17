import unittest

from revoscan_launcher.gpu import (
    AMD_TARGETS,
    GpuAdapter,
    build_mapping_environment,
    parse_pci_id,
)


class GpuMappingTests(unittest.TestCase):
    def test_recognizes_amd_and_intel_pci_vendors(self):
        amd = GpuAdapter.from_pci("0x1002", "0x1900", "Radeon 780M")
        intel = GpuAdapter.from_pci("0x8086", "0x7d55", "Arc Graphics")
        self.assertEqual(amd.vendor, "amd")
        self.assertEqual(intel.vendor, "intel")
        self.assertEqual(parse_pci_id("0x8086"), 0x8086)

    def test_invalid_pci_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_pci_id("not-a-pci-id")

    def test_targets_are_amd_profiles_and_mapping_is_explicit(self):
        self.assertTrue(AMD_TARGETS)
        self.assertTrue(all(t.vendor_id == 0x1002 for t in AMD_TARGETS.values()))
        source = GpuAdapter.from_pci("0x8086", "0x7d55", "Intel Arc Graphics")
        self.assertEqual(build_mapping_environment(source, None), {})
        target = AMD_TARGETS["rx-7700-xt"]
        env = build_mapping_environment(source, target)
        self.assertEqual(env["REVOSCAN_MAP_SOURCE_VENDOR"], "8086")
        self.assertEqual(env["REVOSCAN_MAP_SOURCE_DEVICE"], "7d55")
        self.assertEqual(env["REVOSCAN_MAP_TARGET_VENDOR"], "1002")
        self.assertEqual(env["REVOSCAN_MAP_TARGET_NAME"], target.name)

    def test_mapping_rejects_unknown_source_vendors(self):
        source = GpuAdapter.from_pci("0x10de", "0x2684", "NVIDIA")
        with self.assertRaises(ValueError):
            build_mapping_environment(source, AMD_TARGETS["rx-7700-xt"])


if __name__ == "__main__":
    unittest.main()
