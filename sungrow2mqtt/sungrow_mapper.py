#!/usr/bin/env python3
"""Pure transformation helpers for sungrow2mqtt.

Flatten a Sungrow device's ``REAL`` and ``DIRECT`` measurement lists into a
single ``{name: value}`` payload and turn per-device data into MQTT
(topic, payload) pairs. These functions perform no I/O.
"""

import json
import time


def flatten_measurements(items: list[dict]) -> dict:
    """Flatten a WiNet-S measurement list into a ``{name: value}`` dict.

    Each item is expected to carry a ``data_name`` and ``data_value`` (real
    data) or ``voltage``/``current`` fields (direct data). Items without a
    recognizable name are skipped.

    Args:
        items: A ``real`` or ``direct`` measurement list from the reader.

    Returns:
        Mapping of measurement name to its value.
    """
    flat: dict = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("data_name") or item.get("name")
        if name is None:
            continue
        value = item.get("data_value", item.get("value"))
        unit = item.get("data_unit") or item.get("unit")
        flat[name] = {"value": value, "unit": unit} if unit is not None else value
    return flat


def process_device(device: dict) -> dict:
    """Build a flat payload for a single device.

    Args:
        device: A device dict from the reader, with ``REAL``/``DIRECT`` lists
            and metadata (``dev_id``, ``dev_name``, ...).

    Returns:
        A payload dict with device metadata plus flattened measurements.
    """
    payload: dict = {}
    if device.get("dev_name") is not None:
        payload["dev_name"] = device.get("dev_name")
    if device.get("dev_model") is not None:
        payload["dev_model"] = device.get("dev_model")

    payload.update(flatten_measurements(device.get("REAL", [])))
    payload.update(flatten_measurements(device.get("DIRECT", [])))
    return payload


def build_payload(device_payload: dict) -> str:
    """Serialize a device payload dict to a JSON string with a timestamp.

    A top-level ``timestamp`` key (Unix epoch seconds) is added to every
    published payload.

    Args:
        device_payload: The flattened per-device payload.

    Returns:
        A JSON string suitable for publishing.
    """
    payload = dict(device_payload)
    payload["timestamp"] = int(time.time())
    return json.dumps(payload)


def map_to_topics(devices: list[dict], base_topic: str) -> list[tuple[str, str]]:
    """Transform device data into (topic, payload) pairs.

    Args:
        devices: The device list produced by the reader.
        base_topic: The configured publish base topic; the device id is appended.

    Returns:
        List of (``{base_topic}/{dev_id}``, json_payload) tuples. Devices
        without a ``dev_id`` are skipped.
    """
    topics: list[tuple[str, str]] = []
    for device in devices:
        device_id = device.get("dev_id")
        if device_id is None:
            continue
        payload = process_device(device)
        topics.append((f"{base_topic}/{device_id}", build_payload(payload)))
    return topics
