import asyncio
import unittest

from app.google_search_agent import robot_state
from app.google_search_agent.agent import root_agent
from app.google_search_agent.robot_tools import (
    ALL_ROBOT_TOOLS,
    get_robot_temperature,
    move_robot,
    run_actions_parallel,
    set_emergency_stop,
    set_fan,
    set_light_color,
)


class RobotToolsTests(unittest.TestCase):
    def setUp(self):
        robot_state.reset()

    def test_twenty_implementations_are_split_between_four_agents(self):
        self.assertEqual(20, len(ALL_ROBOT_TOOLS))
        self.assertEqual(4, len(root_agent.tools))
        self.assertEqual(
            {"sensor_agent", "light_sound_agent", "motion_agent", "system_agent"},
            {tool.name for tool in root_agent.tools},
        )
        self.assertEqual(0, len(root_agent.sub_agents))
        self.assertEqual(
            20,
            sum(len(tool.agent.tools) for tool in root_agent.tools),
        )

    def test_temperature_returns_simulated_value(self):
        self.assertEqual(36.5, get_robot_temperature()["temperature"])

    def test_light_state_is_remembered(self):
        self.assertEqual("success", set_light_color("green")["status"])
        self.assertEqual("green", robot_state.read("light_color")["light_color"])

    def test_emergency_stop_blocks_movement(self):
        set_emergency_stop(True)
        self.assertEqual("error", move_robot("forward")["status"])

    def test_independent_actions_can_run_concurrently(self):
        results = asyncio.run(
            run_actions_parallel(
                [(set_light_color, {"color": "blue"}), (set_fan, {"enabled": True})]
            )
        )
        self.assertEqual(["success", "success"], [item["status"] for item in results])


if __name__ == "__main__":
    unittest.main()
