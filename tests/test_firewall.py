"""Tests for firewalld rich-rule handling."""

from __future__ import annotations

import unittest

from revoscan_launcher.network import ensure_firewall_allows, firewall_allows


def fake_runner(responses):
    def run(args, timeout=30.0):
        key = " ".join(args)
        for pattern, value in responses:
            if pattern in key:
                return value
        return ""

    return run


class FirewallTests(unittest.TestCase):
    def test_rule_already_present(self):
        runner = fake_runner([("--state", "running\n"), ("--query-rich-rule", "yes\n")])
        ok, message = ensure_firewall_allows("192.168.179.1", runner)
        self.assertTrue(ok)
        self.assertIn("lready allowed", message)

    def test_rule_already_present_for_subnet(self):
        runner = fake_runner([("--state", "running\n"), ("--query-rich-rule", "yes\n")])
        ok, message = ensure_firewall_allows("192.168.179.0/24", runner)
        self.assertTrue(ok)
        self.assertIn("lready allowed", message)

    def test_adds_rule_via_sudo(self):
        calls = []

        def run(args, timeout=30.0):
            key = " ".join(args)
            calls.append(key)
            if "--state" in key:
                return "running\n"
            if "--query-rich-rule" in key:
                return "no\n"
            if "--add-rich-rule" in key:
                return "success\n"
            return ""

        ok, message = ensure_firewall_allows("192.168.179.0/24", run)
        self.assertTrue(ok)
        self.assertIn("192.168.179.0/24", message)
        self.assertTrue(any("--permanent" in call for call in calls))

    def test_reports_command_when_elevation_missing(self):
        runner = fake_runner([("--state", "running\n"), ("--query-rich-rule", "no\n")])
        ok, message = ensure_firewall_allows("192.168.179.1", runner)
        self.assertFalse(ok)
        self.assertIn("sudo firewall-cmd", message)

    def test_query_parses_yes(self):
        runner = fake_runner([("--query-rich-rule", "yes\n")])
        self.assertTrue(firewall_allows("10.0.0.1", runner))

    def test_query_uses_cidr_form(self):
        calls = []

        def run(args, timeout=30.0):
            calls.append(" ".join(args))
            return "yes\n"

        firewall_allows("192.168.179.0/24", run)
        self.assertIn('source address="192.168.179.0/24"', calls[0])


if __name__ == "__main__":
    unittest.main()
