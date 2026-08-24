import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

import main


class MainCliTests(unittest.TestCase):
    def test_text_mode_is_supported(self):
        args = main.parse_cli_args(["--text"])
        self.assertTrue(args.text)

    def test_default_mode_is_audio_terminal_mode(self):
        args = main.parse_cli_args([])
        self.assertFalse(args.text)

    def test_history_defaults_to_twenty_entries(self):
        args = main.parse_cli_args(["--history"])
        self.assertEqual(20, args.history)

    def test_history_is_rendered_as_dialogue_cards(self):
        history = [{
            "created_at": "2026-08-24T12:00:00+00:00",
            "mode": "voice",
            "user_text": "Işığı yeşil yap.",
            "actions": [{
                "tool_name": "set_light_color",
                "arguments": {"color": "green"},
                "result": {
                    "status": "success",
                    "light_color": "green",
                    "_api_elapsed_ms": 61.2,
                },
            }],
            "assistant_text": "Işık yeşil yapıldı.",
            "usage": [{
                "event_id": "event-1",
                "author": "robot_coordinator",
                "model": "gemini-3.1-flash-live-preview",
                "usage": {
                    "prompt_token_count": 100,
                    "candidates_token_count": 20,
                    "prompt_tokens_details": [
                        {"modality": "AUDIO", "token_count": 100}
                    ],
                    "candidates_tokens_details": [
                        {"modality": "AUDIO", "token_count": 20}
                    ],
                },
            }],
        }]
        output = StringIO()
        with patch(
            "app.google_search_agent.robot_memory.get_history", return_value=history
        ), redirect_stdout(output):
            main._print_history(20)

        rendered = output.getvalue()
        self.assertIn("SEN", rendered)
        self.assertIn("set_light_color", rendered)
        self.assertIn("GEMINI", rendered)
        self.assertIn("MALİYET", rendered)
        self.assertIn("image=0", rendered)
        self.assertIn("video=0", rendered)
        self.assertIn("document=0", rendered)
        self.assertIn("other=0", rendered)
        self.assertIn("Thinking            : 0", rendered)
        self.assertIn("Cache tokenı        : 0", rendered)
        self.assertNotIn("{'color': 'green'}", rendered)

    def test_live_audio_cost_uses_modality_rates(self):
        records = [{
            "author": "robot_coordinator",
            "model": "gemini-3.1-flash-live-preview",
            "usage": {
                "prompt_token_count": 1000,
                "candidates_token_count": 1000,
                "prompt_tokens_details": [
                    {"modality": "AUDIO", "token_count": 1000}
                ],
                "candidates_tokens_details": [
                    {"modality": "AUDIO", "token_count": 1000}
                ],
            },
        }]
        summary = main._usage_summary(records, "voice")
        self.assertEqual((1000, 1000), (summary["input_total"], summary["output_total"]))
        self.assertEqual(1000, summary["input_modalities"]["audio"])
        self.assertEqual(1000, summary["output_modalities"]["audio"])
        self.assertAlmostEqual(0.015, summary["cost_usd"])

    def test_thinking_tool_and_cache_tokens_are_separated(self):
        records = [{
            "author": "sensor_agent",
            "model": "gemini-3.6-flash",
            "usage": {
                "prompt_token_count": 1000,
                "tool_use_prompt_token_count": 100,
                "cached_content_token_count": 200,
                "candidates_token_count": 50,
                "thoughts_token_count": 25,
                "total_token_count": 1175,
            },
        }]
        summary = main._usage_summary(records, "text")
        self.assertEqual(1100, summary["input_total"])
        self.assertEqual(75, summary["output_total"])
        self.assertEqual(100, summary["tool_tokens"])
        self.assertEqual(200, summary["cached_tokens"])
        self.assertEqual(25, summary["thinking_tokens"])
        expected = 900 * 0.75 / 1_000_000
        expected += 200 * 0.075 / 1_000_000
        expected += 75 * 3.75 / 1_000_000
        self.assertAlmostEqual(expected, summary["cost_usd"])

    def test_missing_modality_detail_is_reconciled_as_text(self):
        records = [{
            "author": "robot_coordinator",
            "model": "gemini-3.1-flash-live-preview",
            "usage": {
                "prompt_token_count": 100,
                "candidates_token_count": 50,
                "prompt_tokens_details": [
                    {"modality": "AUDIO", "token_count": 80}
                ],
                "candidates_tokens_details": [
                    {"modality": "AUDIO", "token_count": 40}
                ],
            },
        }]
        summary = main._usage_summary(records, "voice")
        self.assertEqual({"audio": 80, "text": 20}, summary["input_modalities"])
        self.assertEqual({"audio": 40, "text": 10}, summary["output_modalities"])


if __name__ == "__main__":
    unittest.main()
