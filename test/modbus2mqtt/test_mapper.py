#!/usr/bin/env python3
"""Unit tests for modbus2mqtt.modbus_mapper (pure transformation functions)."""

import json

from modbus2mqtt import modbus_mapper


def test_coerce_float_variants():
    assert modbus_mapper.coerce_float(5) == 5.0
    assert modbus_mapper.coerce_float('3.5') == 3.5
    assert modbus_mapper.coerce_float('  10  ') == 10.0
    assert modbus_mapper.coerce_float(None) is None
    assert modbus_mapper.coerce_float('') is None
    assert modbus_mapper.coerce_float('abc') is None
    assert modbus_mapper.coerce_float(True) is None


def test_apply_scale_default_factor():
    assert modbus_mapper.apply_scale(100.0, None) == 100.0
    assert modbus_mapper.apply_scale(100.0, 0.1) == 10.0
    assert modbus_mapper.apply_scale(100.0, '2') == 200.0


def test_clamp_below_min_becomes_zero():
    assert modbus_mapper.clamp(-5.0, 0.0, None) == 0.0


def test_clamp_above_max_is_capped():
    assert modbus_mapper.clamp(500.0, None, 100.0) == 100.0


def test_clamp_within_range_unchanged():
    assert modbus_mapper.clamp(42.0, 0.0, 100.0) == 42.0


def test_clamp_no_bounds():
    assert modbus_mapper.clamp(-999.0, None, None) == -999.0


def test_map_register_scales_and_labels():
    register = {'Name': 'LEVEL', 'Scale Factor': 0.1, 'Unit': 'mm'}
    result = modbus_mapper.map_register(register, 1234)
    assert result == {'VALUE': 123.4, 'UNIT': 'mm'}


def test_process_device_skips_missing_and_none():
    registers = [
        {'Name': 'A', 'Scale Factor': 1, 'Unit': 'V'},
        {'Name': 'B', 'Scale Factor': 1, 'Unit': 'A'},
        {'Name': 'C', 'Scale Factor': 1, 'Unit': 'W'},
    ]
    raw = {'A': 10, 'B': None}  # C missing entirely
    processed = modbus_mapper.process_device(registers, raw)
    assert processed == {'A': {'VALUE': 10.0, 'UNIT': 'V'}}


def test_map_to_topics_builds_topic_and_json():
    data = {9: {'VOLTAGE': {'VALUE': 230.0, 'UNIT': 'V'}}}
    topics = modbus_mapper.map_to_topics(data, 'PLANT/PV')
    assert len(topics) == 1
    topic, payload = topics[0]
    assert topic == 'PLANT/PV/9'
    decoded = json.loads(payload)
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == {'VOLTAGE': {'VALUE': 230.0, 'UNIT': 'V'}}


def test_build_payload_includes_epoch_timestamp():
    import time

    before = int(time.time())
    payload = json.loads(modbus_mapper.build_payload({'X': {'VALUE': 1, 'UNIT': 'V'}}))
    after = int(time.time())

    assert 'timestamp' in payload
    assert isinstance(payload['timestamp'], int)
    assert before <= payload['timestamp'] <= after
    # Original data is preserved alongside the timestamp.
    assert payload['X'] == {'VALUE': 1, 'UNIT': 'V'}


def test_build_payload_does_not_mutate_input():
    original = {'X': {'VALUE': 1, 'UNIT': 'V'}}
    modbus_mapper.build_payload(original)
    assert 'timestamp' not in original
