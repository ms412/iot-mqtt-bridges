#!/usr/bin/env python3
"""Pure transformation helpers for so2mqtt (S0 pulse counters)."""

import json
import logging
import time

__APP__ = "so2mqtt"

_lib_name = str(__name__.rsplit(".", 1)[-1])
_log = logging.getLogger(f"{__APP__}.{_lib_name}")

# Interface-level keys that are not channel definitions.
_INTERFACE_KEYS = {
    "PORT",
    "BAUDRATE",
}


def extract_channel(field_list: list[str], channel_config: dict) -> dict | None:
    """Compute one channel's ``{S0, S0_raw}`` value from the raw field list.

    Reads the field at index ``BYTE``, divides by ``FACTOR``, and adds
    ``OFFSET``.

    Args:
        field_list: The ``;``-separated fields from the adapter response.
        channel_config: Channel config with ``BYTE``, ``FACTOR``, ``OFFSET``.

    Returns:
        A ``{S0, S0_raw}`` dict, or None if the field is missing or unparseable.
    """
    index = int(channel_config.get("BYTE", 0))
    factor = float(channel_config.get("FACTOR", 1)) or 1.0
    offset = float(channel_config.get("OFFSET", 0))

    try:
        raw = field_list[index]
        value = float(raw) / factor + offset
    except (IndexError, ValueError) as exc:
        _log.error("Cannot extract channel (BYTE=%s): %s", index, exc)
        return None

    return {"S0": value, "S0_raw": raw}


def process_interface(interface_config: dict, field_list: list[str]) -> dict:
    """Build ``{channel: {S0, S0_raw}}`` for every channel on an interface.

    Args:
        interface_config: The interface config including its channel entries.
        field_list: The ``;``-separated fields from the adapter response.

    Returns:
        Mapping of channel name to its computed payload.
    """
    channels: dict = {}
    for name, value in interface_config.items():
        if name in _INTERFACE_KEYS or not isinstance(value, dict):
            continue
        channel = extract_channel(field_list, value)
        if channel is None:
            continue
        channels[name] = channel
    return channels


def build_payload(channel_payload: dict) -> str:
    """Serialize a channel payload dict to a JSON string with a timestamp.

    A top-level ``timestamp`` key (Unix epoch seconds) is added to every
    published payload.

    Args:
        channel_payload: A ``{S0, S0_raw}`` dict.

    Returns:
        A JSON string suitable for publishing.
    """
    payload = dict(channel_payload)
    payload["timestamp"] = int(time.time())
    return json.dumps(payload)


def map_to_topics(data: dict, base_topic: str) -> list[tuple[str, str]]:
    """Transform processed data into (topic, payload) pairs.

    Args:
        data: Mapping of interface -> ``{channel: payload}``.
        base_topic: The configured publish base topic.

    Returns:
        List of (``{base_topic}/{interface}/{channel}``, json_payload) tuples.
    """
    topics: list[tuple[str, str]] = []
    for interface, channels in data.items():
        for channel, payload in channels.items():
            topic = f"{base_topic}/{interface}/{channel}"
            topics.append((topic, build_payload(payload)))
    return topics
