#!/usr/bin/env python3
"""SML frame parsing and payload/topic helpers for sml2mqtt."""

import json
import logging
import time

from smllib import SmlStreamReader
from smllib.errors import SmlLibException

from sml2mqtt.sml_obis import OBIS_NAMES, UNITS

__APP__ = "sml2mqtt"

_lib_name = str(__name__.rsplit(".", 1)[-1])
_log = logging.getLogger(f"{__APP__}.{_lib_name}")


def parse_frame(frame_bytes: bytes) -> dict:
    """Parse an SML frame into an OBIS store.

    Args:
        frame_bytes: Raw bytes of a complete SML frame.

    Returns:
        Mapping of OBIS short code to ``{data_value, data_unit, data_type}``.
        Empty when the frame is incomplete or fails to parse.
    """
    store: dict = {}

    stream = SmlStreamReader()
    stream.add(frame_bytes)

    try:
        frame = stream.get_frame()
    except SmlLibException as exc:
        _log.error("Failed to parse SML frame: %s", exc)
        return store

    if frame is None:
        _log.error("Incomplete SML frame; bytes missing")
        return store

    for entry in frame.get_obis():
        store[entry.obis.obis_short] = {
            "data_value": entry.get_value(),
            "data_unit": UNITS.get(entry.unit, None),
            "data_type": OBIS_NAMES.get(entry.obis, None),
        }

    return store


def build_payload(store: dict) -> str:
    """Serialize the parsed OBIS store to a JSON string with a timestamp.

    A top-level ``timestamp`` key (Unix epoch seconds) is added to every
    published payload.

    Args:
        store: Parsed OBIS store.

    Returns:
        A JSON string suitable for publishing.
    """
    payload = dict(store)
    payload["timestamp"] = int(time.time())
    return json.dumps(payload)


def map_to_topics(store: dict, base_topic: str) -> list[tuple[str, str]]:
    """Return the (topic, payload) pair for a parsed SML frame.

    Args:
        store: Parsed OBIS store.
        base_topic: The configured publish topic (the whole frame is published
            to this single topic).

    Returns:
        A one-element list of (topic, json_payload), or empty when the store is
        empty.
    """
    if not store:
        return []
    return [(base_topic, build_payload(store))]
