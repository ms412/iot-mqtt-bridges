#!/usr/bin/env python3
"""Tests for sml2mqtt.sml_obis lookup tables and CRC helper."""

from sml2mqtt import sml_obis


def test_get_crc_known_value():
    # CRC-16/X25 of the canonical check string "123456789".
    assert sml_obis.get_crc(b'123456789') == 0x6E90


def test_units_lookup():
    assert sml_obis.UNITS[30] == 'Wh'
    assert sml_obis.UNITS[27] == 'W'
    assert sml_obis.UNITS[35] == 'V'


def test_obis_names_lookup():
    assert sml_obis.OBIS_NAMES['0100010800ff'].startswith('Z')  # Zaehlerstand Total


def test_frame_markers_are_bytes():
    assert isinstance(sml_obis.SML_START, bytes)
    assert isinstance(sml_obis.SML_END, bytes)
    assert sml_obis.SML_START.startswith(b'\x1b\x1b\x1b\x1b')
