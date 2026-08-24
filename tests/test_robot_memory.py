import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.google_search_agent import robot_memory


class RobotMemoryTests(unittest.TestCase):
    def test_request_and_actions_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            with patch.dict(os.environ, {"ROBOT_MEMORY_DB": str(path)}):
                robot_memory.create_request("request-1", "text", "ışığı yeşil yap")
                robot_memory.add_action(
                    "request-1",
                    "set_light_color",
                    {"color": "green"},
                    {"status": "success", "light_color": "green"},
                )
                robot_memory.update_request(
                    "request-1", assistant_text="Işık yeşil yapıldı."
                )
                robot_memory.add_usage(
                    "request-1",
                    {
                        "event_id": "event-1",
                        "author": "robot_coordinator",
                        "model": "gemini-3.6-flash",
                        "usage": {
                            "prompt_token_count": 100,
                            "candidates_token_count": 20,
                        },
                    },
                )
                history = robot_memory.get_history()

            self.assertTrue(path.exists())
            self.assertEqual("ışığı yeşil yap", history[0]["user_text"])
            self.assertEqual("set_light_color", history[0]["actions"][0]["tool_name"])
            self.assertEqual("green", history[0]["actions"][0]["result"]["light_color"])
            self.assertEqual("Işık yeşil yapıldı.", history[0]["assistant_text"])
            self.assertEqual(100, history[0]["usage"][0]["usage"]["prompt_token_count"])
            with robot_memory._connect() as connection:
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                }
            self.assertEqual({"dialogue_history"}, tables)

    def test_recent_history_is_ordered_oldest_to_newest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.db"
            with patch.dict(os.environ, {"ROBOT_MEMORY_DB": str(path)}):
                robot_memory.create_request("first", "text", "ilk")
                robot_memory.create_request("second", "text", "ikinci")
                robot_memory.create_request("third", "text", "üçüncü")
                history = robot_memory.get_history(limit=2)

            self.assertEqual(["ikinci", "üçüncü"], [item["user_text"] for item in history])


if __name__ == "__main__":
    unittest.main()
