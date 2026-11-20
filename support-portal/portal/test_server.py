import os
import unittest

os.environ.setdefault("RUSTDESK_HOST", "support.example.com")
os.environ.setdefault("RUSTDESK_KEY", "OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=")

import server  # noqa: E402


class FileNameTest(unittest.TestCase):
    def test_download_name_round_trips(self):
        cfg = server.server_config()
        name = server.download_name(cfg)
        self.assertIn("-qs-", name)
        self.assertTrue(name.endswith(".exe"))
        self.assertNotIn("/", name)
        self.assertEqual(server.decode_config(name), cfg)

    def test_browser_duplicate_suffix_still_parses(self):
        cfg = server.server_config()
        name = server.download_name(cfg)[:-4] + " (1).exe"
        self.assertEqual(server.decode_config(name), cfg)

    def test_token_never_contains_separator(self):
        for i in range(300):
            cfg = {"host": f"h{i}.example.com", "key": "k" * (i % 50)}
            token = server.encode_config(cfg)
            self.assertNotIn("--", token)
            self.assertFalse(token.startswith("-"))


if __name__ == "__main__":
    unittest.main()
