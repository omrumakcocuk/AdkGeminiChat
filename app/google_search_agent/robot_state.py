"""Thread-safe in-memory state for the demo robot."""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any


_LOCK = RLock()
_DEFAULT_STATE: dict[str, Any] = {
    "temperature_c": 36.5,
    "battery_percent": 82,
    "humidity_percent": 41,
    "distance_cm": 125.0,
    "ambient_light_lux": 320,
    "light_color": "off",
    "light_brightness_percent": 100,
    "fan_enabled": False,
    "fan_speed_percent": 0,
    "motor_enabled": False,
    "speed_percent": 0,
    "direction": "stopped",
    "buzzer_enabled": False,
    "buzzer_frequency_hz": 440,
    "camera_enabled": False,
    "camera_angle_degrees": 0,
    "mode": "manual",
    "emergency_stop": False,
}
_state = deepcopy(_DEFAULT_STATE)


def read(*keys: str) -> dict[str, Any]:
    """Return a consistent snapshot of selected state values."""
    with _LOCK:
        return {key: deepcopy(_state[key]) for key in keys}


def update(**values: Any) -> dict[str, Any]:
    """Atomically update and return selected state values."""
    with _LOCK:
        _state.update(values)
        return {key: deepcopy(_state[key]) for key in values}


def snapshot() -> dict[str, Any]:
    """Return the complete simulated robot state."""
    with _LOCK:
        return deepcopy(_state)


def reset() -> dict[str, Any]:
    """Reset all simulated values to their startup defaults."""
    with _LOCK:
        _state.clear()
        _state.update(deepcopy(_DEFAULT_STATE))
        return deepcopy(_state)
