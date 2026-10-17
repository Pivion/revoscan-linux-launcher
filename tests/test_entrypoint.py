import unittest

from revoscan_launcher.entrypoint import run


class EntrypointTests(unittest.TestCase):
    def test_run_delegates_to_launcher_main(self):
        calls = []
        run(lambda: calls.append("started"))
        self.assertEqual(calls, ["started"])


if __name__ == "__main__":
    unittest.main()
