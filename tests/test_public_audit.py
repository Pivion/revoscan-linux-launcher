import tempfile
import unittest
from pathlib import Path

from revoscan_launcher.public_audit import audit_tree


class PublicAuditTests(unittest.TestCase):
    def test_clean_launcher_payload_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "AppRun").write_text("exec launcher\n")
            (root / "launcher.py").write_text("print('hello')\n")
            self.assertEqual(audit_tree(root), [])

    def test_rejects_vendor_application_prefix_and_user_scan_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "usr/share/doc").mkdir(parents=True)
            (root / "usr/share/doc/app.log").write_text("runtime log")
            (root / "home/user/drive_c/Program Files/Revo Scan 6/RevoScan6.exe").parent.mkdir(parents=True)
            (root / "home/user/drive_c/Program Files/Revo Scan 6/RevoScan6.exe").write_text("licensed payload")
            (root / "home/user/Project.revox").write_text("scan project")
            problems = audit_tree(root)
            self.assertGreaterEqual(len(problems), 3)
            self.assertTrue(any("drive_c" in item for item in problems))
            self.assertTrue(any(".revox" in item for item in problems))
            self.assertTrue(any(".log" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
