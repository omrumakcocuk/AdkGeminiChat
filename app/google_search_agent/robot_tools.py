"""ADK function tools for a simulated robot.

These functions intentionally perform no hardware I/O. They expose the same
shape that real HTTP, ROS or serial adapters can implement later.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from . import robot_api_client as robot_state


COLORS = {"off", "red", "green", "blue", "yellow", "white", "purple", "orange"}
DIRECTIONS = {"forward", "backward", "left", "right", "stopped"}
MODES = {"manual", "automatic", "sleep", "demo"}


def _ok(**data: Any) -> dict[str, Any]:
    return {
        "status": "success",
        **data,
        "_api_elapsed_ms": round(robot_state.consume_timing_ms(), 3),
    }


def _error(message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "message": message,
        "_api_elapsed_ms": round(robot_state.consume_timing_ms(), 3),
    }


def _percent(value: int, field: str) -> dict[str, Any] | None:
    if not 0 <= value <= 100:
        return _error(f"{field} must be between 0 and 100")
    return None


# Sensor tools (5)
def get_robot_temperature() -> dict[str, Any]:
    """Read the robot's simulated internal temperature in Celsius."""
    value = robot_state.read("temperature_c")["temperature_c"]
    return _ok(temperature=value, unit="celsius")


def get_battery_level() -> dict[str, Any]:
    """Read the robot's simulated battery charge percentage."""
    value = robot_state.read("battery_percent")["battery_percent"]
    return _ok(battery=value, unit="percent")


def get_humidity() -> dict[str, Any]:
    """Read the simulated humidity around the robot as a percentage."""
    value = robot_state.read("humidity_percent")["humidity_percent"]
    return _ok(humidity=value, unit="percent")


def get_obstacle_distance() -> dict[str, Any]:
    """Read the simulated distance to the closest obstacle in centimeters."""
    value = robot_state.read("distance_cm")["distance_cm"]
    return _ok(distance=value, unit="centimeter")


def get_ambient_light() -> dict[str, Any]:
    """Read the simulated ambient light level in lux."""
    value = robot_state.read("ambient_light_lux")["ambient_light_lux"]
    return _ok(ambient_light=value, unit="lux")


# Light and sound tools (5)
def set_light_color(color: str) -> dict[str, Any]:
    """Set the robot light color. Supported colors: off, red, green, blue, yellow, white, purple, orange."""
    normalized = color.strip().lower()
    if normalized not in COLORS:
        return _error(f"unsupported color: {color}")
    robot_state.update(light_color=normalized)
    return _ok(light_color=normalized)


def get_light_status() -> dict[str, Any]:
    """Read the robot's current light color and brightness."""
    values = robot_state.read("light_color", "light_brightness_percent")
    return _ok(**values)


def set_light_brightness(brightness_percent: int) -> dict[str, Any]:
    """Set the robot light brightness from 0 to 100 percent."""
    if error := _percent(brightness_percent, "brightness_percent"):
        return error
    robot_state.update(light_brightness_percent=brightness_percent)
    return _ok(brightness_percent=brightness_percent)


def set_buzzer(enabled: bool) -> dict[str, Any]:
    """Turn the robot's simulated buzzer on or off."""
    robot_state.update(buzzer_enabled=enabled)
    return _ok(buzzer_enabled=enabled)


def set_buzzer_frequency(frequency_hz: int) -> dict[str, Any]:
    """Set the simulated buzzer frequency between 20 and 20000 Hertz."""
    if not 20 <= frequency_hz <= 20_000:
        return _error("frequency_hz must be between 20 and 20000")
    robot_state.update(buzzer_frequency_hz=frequency_hz)
    return _ok(buzzer_frequency_hz=frequency_hz)


# Movement tools (5)
def move_robot(direction: str, speed_percent: int = 50) -> dict[str, Any]:
    """Move the robot forward, backward, left or right at a percentage speed."""
    normalized = direction.strip().lower()
    if normalized not in DIRECTIONS - {"stopped"}:
        return _error(f"unsupported direction: {direction}")
    if error := _percent(speed_percent, "speed_percent"):
        return error
    if robot_state.read("emergency_stop")["emergency_stop"]:
        return _error("movement blocked because emergency stop is active")
    robot_state.update(
        motor_enabled=True,
        direction=normalized,
        speed_percent=speed_percent,
    )
    return _ok(direction=normalized, speed_percent=speed_percent)


def stop_robot() -> dict[str, Any]:
    """Stop all simulated robot movement immediately."""
    robot_state.update(motor_enabled=False, direction="stopped", speed_percent=0)
    return _ok(direction="stopped", speed_percent=0)


def get_motion_status() -> dict[str, Any]:
    """Read whether the robot is moving, its direction and its speed."""
    values = robot_state.read("motor_enabled", "direction", "speed_percent")
    return _ok(**values)


def set_fan(enabled: bool) -> dict[str, Any]:
    """Turn the robot's simulated cooling fan on or off."""
    speed = 50 if enabled and robot_state.read("fan_speed_percent")["fan_speed_percent"] == 0 else robot_state.read("fan_speed_percent")["fan_speed_percent"]
    robot_state.update(fan_enabled=enabled, fan_speed_percent=speed if enabled else 0)
    return _ok(fan_enabled=enabled, fan_speed_percent=speed if enabled else 0)


def set_fan_speed(speed_percent: int) -> dict[str, Any]:
    """Set cooling fan speed from 0 to 100 percent; zero turns it off."""
    if error := _percent(speed_percent, "speed_percent"):
        return error
    robot_state.update(fan_enabled=speed_percent > 0, fan_speed_percent=speed_percent)
    return _ok(fan_enabled=speed_percent > 0, fan_speed_percent=speed_percent)


# System and camera tools (5)
def set_camera(enabled: bool) -> dict[str, Any]:
    """Turn the robot's simulated camera on or off."""
    robot_state.update(camera_enabled=enabled)
    return _ok(camera_enabled=enabled)


def set_camera_angle(angle_degrees: int) -> dict[str, Any]:
    """Set the simulated camera angle from -90 to 90 degrees."""
    if not -90 <= angle_degrees <= 90:
        return _error("angle_degrees must be between -90 and 90")
    robot_state.update(camera_angle_degrees=angle_degrees)
    return _ok(camera_angle_degrees=angle_degrees)


def set_robot_mode(mode: str) -> dict[str, Any]:
    """Set robot mode to manual, automatic, sleep or demo."""
    normalized = mode.strip().lower()
    if normalized not in MODES:
        return _error(f"unsupported mode: {mode}")
    robot_state.update(mode=normalized)
    return _ok(mode=normalized)


def set_emergency_stop(enabled: bool) -> dict[str, Any]:
    """Enable or release the simulated emergency stop."""
    updates: dict[str, Any] = {"emergency_stop": enabled}
    if enabled:
        updates.update(motor_enabled=False, direction="stopped", speed_percent=0)
    robot_state.update(**updates)
    return _ok(emergency_stop=enabled)


def get_robot_status() -> dict[str, Any]:
    """Read a complete snapshot of all simulated robot sensors and actuators."""
    return _ok(**robot_state.snapshot())


SENSOR_TOOLS = [
    get_robot_temperature,
    get_battery_level,
    get_humidity,
    get_obstacle_distance,
    get_ambient_light,
]
LIGHT_SOUND_TOOLS = [
    set_light_color,
    get_light_status,
    set_light_brightness,
    set_buzzer,
    set_buzzer_frequency,
]
MOTION_TOOLS = [
    move_robot,
    stop_robot,
    get_motion_status,
    set_fan,
    set_fan_speed,
]
SYSTEM_TOOLS = [
    set_camera,
    set_camera_angle,
    set_robot_mode,
    set_emergency_stop,
    get_robot_status,
]
ALL_ROBOT_TOOLS = SENSOR_TOOLS + LIGHT_SOUND_TOOLS + MOTION_TOOLS + SYSTEM_TOOLS


async def run_actions_parallel(actions: list[tuple[Callable[..., dict[str, Any]], dict[str, Any]]]) -> list[dict[str, Any]]:
    """Run independent local/API-style actions concurrently.

    This helper is ready for later async HTTP adapters and is deliberately not
    registered as an LLM tool because callable objects cannot form a useful
    function-call JSON schema.
    """
    return await asyncio.gather(
        *(asyncio.to_thread(function, **arguments) for function, arguments in actions)
    )
