import unittest

from revoscan_launcher.installer import (
    discover_official_installers,
    validate_installer_url,
)


class InstallerDiscoveryTests(unittest.TestCase):
    def test_finds_and_sorts_official_x64_installers(self):
        html = '''
        <a href="https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.3.1.986-windows-x86_64.exe">Download</a>
        <a href="https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.3.2.1028-windows-x86_64.exe">Latest</a>
        <a href="https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.4.1.1088-windows-arm64.exe">Wrong arch</a>
        '''
        releases = discover_official_installers(html)
        self.assertEqual([r.version for r in releases], ["6.3.2.1028", "6.3.1.986"])
        self.assertEqual(releases[0].url, "https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.3.2.1028-windows-x86_64.exe")

    def test_ignores_non_https_and_untrusted_hosts(self):
        html = '''
        <a href="http://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.4.1.1-windows-x86_64.exe">http</a>
        <a href="https://evil.example/RevoScan6-9.9.9-windows-x86_64.exe">evil</a>
        '''
        self.assertEqual(discover_official_installers(html), [])

    def test_final_redirect_must_remain_on_official_download_host(self):
        self.assertTrue(validate_installer_url(
            "https://dl.revopoint3d.com/softs/revoscan6/RevoScan6-6.3.2.1028-windows-x86_64.exe"
        ))
        self.assertFalse(validate_installer_url(
            "https://drive.google.com/file/d/123/view"
        ))


if __name__ == "__main__":
    unittest.main()
