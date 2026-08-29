#!/usr/bin/env python3
"""Tests for SmlReader serial framing and CRC validation."""

from sml2mqtt.sml_reader import SmlReader
from sml2mqtt.sml_obis import SML_START, SML_END, get_crc

SML_CFG = {'SERIAL': '/dev/ttyUSB0', 'BAUDRATE': 9600}


def _build_valid_buffer():
    """Build a buffer with START/END markers and a matching CRC trailer."""
    body = SML_START + b'\x00\x11\x22' + SML_END + b'\x00'  # arbitrary framed body
    crc = get_crc(body)
    return body + bytes([crc >> 8 & 0xFF, crc & 0xFF])


def test_read_frame_returns_none_without_markers(mocker):
    reader = SmlReader(SML_CFG)
    mocker.patch.object(reader, '_read_buffer', return_value=b'no markers here')
    assert reader.read_frame() is None


def test_read_frame_rejects_bad_crc(mocker):
    bad = SML_START + b'\x00\x11' + SML_END + b'\x00\xAB\xCD'  # trailing CRC won't match
    reader = SmlReader(SML_CFG)
    mocker.patch.object(reader, '_read_buffer', return_value=bad)
    assert reader.read_frame() is None


def test_read_frame_accepts_valid_crc(mocker):
    buffer = _build_valid_buffer()
    reader = SmlReader(SML_CFG)
    mocker.patch.object(reader, '_read_buffer', return_value=buffer)
    frame = reader.read_frame()
    assert frame is not None
    assert frame.startswith(SML_START)


def test_connect_opens_serial(mocker):
    serial_ctor = mocker.patch('sml2mqtt.sml_reader.serial.Serial')
    reader = SmlReader(SML_CFG)
    reader.connect()
    serial_ctor.assert_called_once()
