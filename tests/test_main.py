import unittest

import main


class MainCliTests(unittest.TestCase):
    def test_text_mode_is_supported(self):
        args = main.parse_cli_args(["--text"])
        self.assertTrue(args.text)

    def test_default_mode_is_audio_terminal_mode(self):
        args = main.parse_cli_args([])
        self.assertFalse(args.text)


if __name__ == "__main__":
    unittest.main()
