#!/usr/bin/env python3
"""Unit tests for so2mqtt.so_mapper (pure transformation functions)."""

import json

from so2mqtt import so_mapper


def test_extract_channel_applies_factor_and_offset():
    fields = ['header', '5000', '300', 'trailer']
    cfg = {'BYTE': 1, 'FACTOR': 100, 'OFFSET': 2158}
    # 5000 / 100 + 2158 = 2208.0
    assert so_mapper.extract_channel(fields, cfg) == {'S0': 2208.0, 'S0_raw': '5000'}


def test_extract_channel_second_field():
    fields = ['header', '5000', '300', 'trailer']
    cfg = {'BYTE': 2, 'FACTOR': 100, 'OFFSET': 10}
    # 300 / 100 + 10 = 13.0
    assert so_mapper.extract_channel(fields, cfg) == {'S0': 13.0, 'S0_raw': '300'}


def test_extract_channel_out_of_range_returns_none():
    assert so_mapper.extract_channel(['only'], {'BYTE': 5, 'FACTOR': 1, 'OFFSET': 0}) is None


def test_extract_channel_non_numeric_returns_none():
    assert so_mapper.extract_channel(['x', 'abc'], {'BYTE': 1, 'FACTOR': 1, 'OFFSET': 0}) is None


def test_process_interface_builds_channels():
    interface_cfg = {
        'PORT': '/dev/ttyUSB1',
        'BAUDRATE': 38400,
        'GAS01': {'BYTE': 1, 'FACTOR': 100, 'OFFSET': 2158},
        'S0-2': {'BYTE': 2, 'FACTOR': 100, 'OFFSET': 10},
    }
    fields = ['h', '5000', '300']
    channels = so_mapper.process_interface(interface_cfg, fields)
    assert channels['GAS01'] == {'S0': 2208.0, 'S0_raw': '5000'}
    assert channels['S0-2'] == {'S0': 13.0, 'S0_raw': '300'}
    # PORT/BAUDRATE are not treated as channels.
    assert set(channels.keys()) == {'GAS01', 'S0-2'}


def test_map_to_topics_nested_topic():
    data = {'SERIAL01': {'GAS01': {'S0': 2208.0, 'S0_raw': '5000'}}}
    topics = so_mapper.map_to_topics(data, 'HOME/S0')
    assert len(topics) == 1
    topic, payload = topics[0]
    assert topic == 'HOME/S0/SERIAL01/GAS01'
    decoded = json.loads(payload)
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == {'S0': 2208.0, 'S0_raw': '5000'}
