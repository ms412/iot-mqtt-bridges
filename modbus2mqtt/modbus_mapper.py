#!/usr/bin/env python3
"""Pure transformation helpers for modbus2mqtt.

These functions apply scaling and value-range clamping to raw register readings
and turn them into MQTT (topic, payload) pairs. They perform no I/O.
"""

import json


def coerce_float(value: object) -> float | None:
    """Convert a YAML value to float, tolerating strings and blanks.

    Args:
        value: A value that may be an int, float, or numeric string.

    Returns:
        The value as a float, or None when no valid number is present.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def apply_scale(value: float, scale_factor: object) -> float:
    """Scale a raw register value by its scale factor.

    Args:
        value: Raw decoded register value.
        scale_factor: Multiplier from the register definition (defaults to 1).

    Returns:
        The scaled value.
    """
    factor = coerce_float(scale_factor)
    if factor is None:
        factor = 1.0
    return float(value) * factor


def clamp(value: float, minimum: float | None, maximum: float | None) -> float:
    """Clamp a scaled value to the configured range.

    Args:
        value: Scaled register value.
        minimum: Lower bound; values below it become 0. None disables the check.
        maximum: Upper bound; values above it are capped. None disables the check.

    Returns:
        The clamped value.
    """
    if minimum is not None and value < minimum:
        value = 0.0
    if maximum is not None and value > maximum:
        value = maximum
    return value


def map_register(register: dict, raw_value: object) -> dict:
    """Turn a single raw reading into a ``{VALUE, UNIT}`` entry.

    Args:
        register: The register definition (Scale Factor, Unit, Value Range ...).
        raw_value: The raw decoded value read from the device.

    Returns:
        A dict with the scaled/clamped ``VALUE`` and its ``UNIT``.
    """
    value = apply_scale(float(raw_value), register.get("Scale Factor", 1))
    value = clamp(
        value,
        coerce_float(register.get("Value Range min")),
        coerce_float(register.get("Value Range max")),
    )
    return {"VALUE": value, "UNIT": register.get("Unit")}


def process_device(registers: list[dict], raw_values: dict) -> dict:
    """Build a device payload from register definitions and raw readings.

    Args:
        registers: The register definitions for this device.
        raw_values: Mapping of register name to raw value; entries missing or
            with a None value are skipped.

    Returns:
        Mapping of register name to ``{VALUE, UNIT}`` entries.
    """
    payload: dict = {}
    for register in registers:
        name = register.get("Name")
        raw_value = raw_values.get(name)
        if raw_value is None:
            continue
        payload[name] = map_register(register, raw_value)
    return payload


def build_payload(device_payload: dict) -> str:
    """Serialize a device payload dict to a JSON string.

    Args:
        device_payload: Mapping of register name to ``{VALUE, UNIT}`` entries.

    Returns:
        A JSON string suitable for publishing.
    """
    return json.dumps(device_payload)


def map_to_topics(data: dict, base_topic: str) -> list[tuple[str, str]]:
    """Transform processed per-device data into (topic, payload) pairs.

    Args:
        data: Mapping of device id to processed ``{name: {VALUE, UNIT}}`` dicts.
        base_topic: The configured publish base topic; the device id is appended.

    Returns:
        List of (topic, json_payload) tuples ready to publish.
    """
    topics: list[tuple[str, str]] = []
    for device_id, device_payload in data.items():
        topic = f"{base_topic}/{device_id}"
        topics.append((topic, build_payload(device_payload)))
    return topics
