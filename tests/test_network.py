"""Tests for scanner-subnet detection and firewalld status/allowance."""

from __future__ import annotations

import unittest

from revoscan_launcher.network import (
    FirewallReport,
    default_route_device,
    firewall_report,
    ipv4_links,
    rich_rule,
    scanner_subnets,
)


def fake_runner(responses):
    def run(args, timeout=30.0):
        key = " ".join(args)
        for pattern, value in responses:
            if pattern in key:
                return value
        return ""

    return run


ROUTE = "default via 192.168.8.1 dev wlp0s20f3 proto dhcp metric 600\n"

ADDRS = (
    "1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever\n"
    "2: wlp0s20f3    inet 192.168.8.158/24 brd 192.168.8.255 scope global dynamic noprefixroute wlp0s20f3\\"
    "       valid_lft 3362sec preferred_lft 3362sec\n"
    "3: wlp0s13f0u1u2    inet 192.168.179.120/24 brd 192.168.179.255 scope global noprefixroute "
    "wlp0s13f0u1u2\\       valid_lft forever preferred_lft forever\n"
    "4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\"
    "       valid_lft forever preferred_lft forever\n"
)


class LinkTests(unittest.TestCase):
    def test_parses_ipv4_links_and_skips_loopback(self):
        runner = fake_runner([("ip -o -4 addr", ADDRS), ("ip route", ROUTE)])
        links = ipv4_links(runner)
        self.assertEqual(
            [(link.device, link.address, link.cidr) for link in links],
            [
                ("wlp0s20f3", "192.168.8.158", "192.168.8.0/24"),
                ("wlp0s13f0u1u2", "192.168.179.120", "192.168.179.0/24"),
                ("docker0", "172.17.0.1", "172.17.0.0/16"),
            ],
        )

    def test_normalises_host_bits_to_network_address(self):
        runner = fake_runner([("ip -o -4 addr", "7: wlx1    inet 10.11.12.13/20 scope global wlx1\\\n")])
        self.assertEqual(ipv4_links(runner)[0].cidr, "10.11.0.0/20")

    def test_scanner_subnets_exclude_the_default_route_interface(self):
        runner = fake_runner([("ip -o -4 addr", ADDRS), ("ip route", ROUTE)])
        subnets = [link.cidr for link in scanner_subnets(runner)]
        self.assertIn("192.168.179.0/24", subnets)
        self.assertNotIn("192.168.8.0/24", subnets)

    def test_default_route_device(self):
        runner = fake_runner([("ip route", ROUTE)])
        self.assertEqual(default_route_device(runner), "wlp0s20f3")

    def test_rich_rule_uses_cidr(self):
        self.assertEqual(
            rich_rule("192.168.179.0/24"),
            'rule family="ipv4" source address="192.168.179.0/24" accept',
        )
        self.assertEqual(
            rich_rule("192.168.179.1"),
            'rule family="ipv4" source address="192.168.179.1/32" accept',
        )

    def test_rich_rule_rejects_garbage(self):
        with self.assertRaises(ValueError):
            rich_rule("not-a-subnet")


class FirewallReportTests(unittest.TestCase):
    def test_running_and_allowed(self):
        runner = fake_runner(
            [("--state", "running\n"), ("--query-rich-rule", "yes\n")]
        )
        report = firewall_report(["192.168.179.0/24"], runner)
        self.assertTrue(report.ok)
        self.assertEqual(report.allowed, ("192.168.179.0/24",))
        self.assertIn("already allows", report.describe())

    def test_running_and_blocked(self):
        runner = fake_runner([("--state", "running\n"), ("--query-rich-rule", "no\n")])
        report = firewall_report(["192.168.179.0/24"], runner)
        self.assertFalse(report.ok)
        self.assertEqual(report.missing, ("192.168.179.0/24",))
        self.assertIn("Allow scanner", report.describe())

    def test_firewalld_not_running_needs_no_rule(self):
        runner = fake_runner([("--state", "not running\n")])
        report = firewall_report(["192.168.179.0/24"], runner)
        self.assertTrue(report.ok)
        self.assertIn("Firewall is off", report.describe())

    def test_empty_subnets_explain_how_to_attach_the_adapter(self):
        runner = fake_runner([("--state", "running\n")])
        report = firewall_report([], runner)
        self.assertTrue(report.ok)
        self.assertIn("spare", report.describe().lower())

    def test_report_is_hashable_value_object(self):
        report = FirewallReport(state="running", allowed=(), missing=("10.0.0.0/24",))
        self.assertEqual(report, FirewallReport(state="running", allowed=(), missing=("10.0.0.0/24",)))


if __name__ == "__main__":
    unittest.main()
