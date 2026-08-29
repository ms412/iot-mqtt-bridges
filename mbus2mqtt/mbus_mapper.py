#!/usr/bin/env python3
"""Pure transformation helpers for mbus2mqtt."""

import json
import time


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


def apply_offset(value: float, offset: object) -> float:
    """Add the configured additive offset to a raw reading.

    Args:
        value: Raw meter reading.
        offset: Additive offset from the slave config (defaults to 0).

    Returns:
        The offset-adjusted value.
    """
    resolved = coerce_float(offset)
    if resolved is None:
        resolved = 0.0
    return float(value) + resolved


def map_slave(slave_config: dict, raw_value: float) -> dict:
    """Turn a single raw reading into a ``{metric: value}`` payload.

    Args:
        slave_config: The slave config with optional ``METRIC`` and ``OFFSET``.
        raw_value: The raw meter reading.

    Returns:
        A single-entry dict keyed by the metric label (default ``WATER``).
    """
    metric = slave_config.get("METRIC", "WATER")
    value = apply_offset(raw_value, slave_config.get("OFFSET", 0.0))
    return {metric: value}


def build_payload(slave_payload: dict) -> str:
    """Serialize a slave payload dict to a JSON string with a timestamp.

    A top-level ``timestamp`` key (Unix epoch seconds) is added to every
    published payload.

    Args:
        slave_payload: Mapping of metric label to value.

    Returns:
        A JSON string suitable for publishing.
    """
    payload = dict(slave_payload)
    payload["timestamp"] = int(time.time())
    return json.dumps(payload)


def map_to_topics(data: dict, base_topic: str) -> list[tuple[str, str]]:
    """Transform processed per-slave data into (topic, payload) pairs.

    Args:
        data: Mapping of slave id to processed ``{metric: value}`` dicts.
        base_topic: The configured publish base topic; the slave id is appended.

    Returns:
        List of (topic, json_payload) tuples ready to publish.
    """
    topics: list[tuple[str, str]] = []
    for slave_id, slave_payload in data.items():
        topic = f"{base_topic}/{slave_id}"
        topics.append((topic, build_payload(slave_payload)))
    return topics
