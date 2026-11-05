"""Tests for scanner Wi-Fi discovery and never-default routing."""

from __future__ import annotations

import unittest

from revoscan_launcher.network import (
    WifiNetwork,
    connect_network,
    default_route_device,
    device_gateway,
    scanner_candidates,
    find_scanner_network,
    is_scanner_ssid,
    make_connection_never_default,
    scan_networks,
    scanner_reachable,
    wifi_devices,
)


def fake_runner(responses):
    def run(args, timeout=30.0):
        key = " ".join(args)
        for pattern, value in responses:
            if pattern in key:
                return value
        return ""

    return run


class SsidTests(unittest.TestCase):
    def test_scanner_ssids(self):
        self.assertTrue(is_scanner_ssid("POP4-REVO-D2682977"))
        self.assertTrue(is_scanner_ssid("REVO-SCAN-AP"))
        self.assertTrue(is_scanner_ssid("Miraco-1234"))

    def test_other_ssids(self):
        self.assertFalse(is_scanner_ssid("B14_5G"))
        self.assertFalse(is_scanner_ssid("AMPR 2.4"))
        self.assertFalse(is_scanner_ssid(""))


class ScanTests(unittest.TestCase):
    def test_parses_network_list(self):
        out = (
            "B14_5G:CA\\:96\\:C5\\:7B\\:F9\\:C5:WPA2 WPA3:99:36\n"
            "POP4-REVO-D2682977:42\\:FD\\:F3\\:FD\\:10\\:EA:--:100:149\n"
            ":96\\:30\\:66\\:40\\:C0\\:EE:WPA2:72:11\n"
            "bogus\n"
        )
        runner = fake_runner([("wifi list", out)])
        networks = scan_networks("wlp0s13f0u1u2", runner)
        self.assertEqual(len(networks), 2)
        scanner = find_scanner_network(networks)
        self.assertIsNotNone(scanner)
        self.assertEqual(scanner.ssid, "POP4-REVO-D2682977")
        self.assertEqual(scanner.bssid, "42:FD:F3:FD:10:EA")
        self.assertEqual(scanner.channel, 149)
        non_scanner = [net for net in networks if net.ssid == "B14_5G"]
        self.assertTrue(non_scanner and not non_scanner[0].is_scanner)

    def test_find_scanner_prefers_strongest(self):
        nets = [
            WifiNetwork("POP4-REVO-1", "aa:aa", "--", 40, 149),
            WifiNetwork("POP4-REVO-2", "bb:bb", "--", 80, 36),
            WifiNetwork("Home", "cc:cc", "WPA2", 90, 11),
        ]
        self.assertEqual(find_scanner_network(nets).ssid, "POP4-REVO-2")
        self.assertIsNone(find_scanner_network([nets[2]]))

    def test_open_network_is_candidate_even_without_vendor_name(self):
        nets = [
            WifiNetwork("MyPrinter-AP", "aa:aa", "", 60, 6),
            WifiNetwork("Home", "cc:cc", "WPA2", 90, 11),
        ]
        self.assertEqual(find_scanner_network(nets).ssid, "MyPrinter-AP")
        candidates = scanner_candidates(nets)
        self.assertEqual([net.ssid for net in candidates], ["MyPrinter-AP"])

    def test_candidates_put_vendor_named_first(self):
        nets = [
            WifiNetwork("FreeWifi", "aa:aa", "", 95, 6),
            WifiNetwork("POP4-REVO-D2682977", "bb:bb", "", 50, 149),
        ]
        self.assertEqual([net.ssid for net in scanner_candidates(nets)][0], "POP4-REVO-D2682977")


class DeviceTests(unittest.TestCase):
    def test_wifi_devices_filters_p2p(self):
        out = (
            "wlp0s20f3:wifi:connected:B14_5G\n"
            "p2p-dev-wlp0s20f3:wifi-p2p:disconnected:\n"
            "wlp0s13f0u1u2:wifi:disconnected:\n"
            "enp0s13f0u1u1:ethernet:unavailable:\n"
        )
        runner = fake_runner([("device status", out)])
        devices = wifi_devices(runner)
        self.assertEqual([d.device for d in devices], ["wlp0s20f3", "wlp0s13f0u1u2"])

    def test_default_route(self):
        runner = fake_runner(
            [("ip route", "default via 192.168.8.1 dev wlp0s20f3 metric 600\n")]
        )
        self.assertEqual(default_route_device(runner), "wlp0s20f3")

    def test_gateway(self):
        runner = fake_runner([("IP4.GATEWAY", "IP4.GATEWAY:192.168.179.1\n")])
        self.assertEqual(device_gateway("wlp0s13f0u1u2", runner), "192.168.179.1")


class ConnectTests(unittest.TestCase):
    def test_connect_marks_never_default(self):
        calls = []

        def runner(args, timeout=30.0):
            calls.append(" ".join(args))
            if "connect POP4-REVO-D2682977" in " ".join(args):
                return "Device 'wlp0s13f0u1u2' successfully activated"
            if "DEVICE,UUID" in " ".join(args):
                return "wlp0s13f0u1u2:abc-123\n"
            return ""

        self.assertTrue(connect_network("wlp0s13f0u1u2", "POP4-REVO-D2682977", runner))
        joined = "\n".join(calls)
        self.assertIn("connection modify abc-123 ipv4.never-default yes", joined)
        self.assertIn("connection modify abc-123 ipv6.never-default yes", joined)

    def test_make_never_default_without_uuid(self):
        runner = fake_runner([])
        self.assertFalse(make_connection_never_default("wlp9", runner))

    def test_ping_check(self):
        good = fake_runner([("ping", "2 packets transmitted, 2 received, 0% packet loss")])
        bad = fake_runner([("ping", "100% packet loss")])
        self.assertTrue(scanner_reachable("192.168.179.1", good))
        self.assertFalse(scanner_reachable("192.168.179.1", bad))


if __name__ == "__main__":
    unittest.main()