import unittest
from unittest.mock import patch

from revoscan_launcher.installer import create_https_context


class TlsContextTests(unittest.TestCase):
    def test_context_uses_bundled_ca_bundle_when_available(self):
        with patch(
            "revoscan_launcher.installer.default_ca_bundle",
            return_value="/app/certifi/cacert.pem",
        ), patch("revoscan_launcher.installer.ssl.create_default_context") as create:
            create_https_context()
            create.assert_called_once_with(cafile="/app/certifi/cacert.pem")

    def test_context_falls_back_to_system_store_when_no_bundle_is_available(self):
        with patch(
            "revoscan_launcher.installer.default_ca_bundle",
            return_value=None,
        ), patch("revoscan_launcher.installer.ssl.create_default_context") as create:
            create_https_context()
            create.assert_called_once_with(cafile=None)


if __name__ == "__main__":
    unittest.main()
