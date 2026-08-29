#!/usr/bin/env python3
"""Unit tests for mbus2mqtt.mbus_mapper (pure transformation functions)."""

import json

from mbus2mqtt import mbus_mapper


def test_apply_offset_default_zero():
    assert mbus_mapper.apply_offset(100.0, None) == 100.0
    assert mbus_mapper.apply_offset(100.0, 5.5) == 105.5
    assert mbus_mapper.apply_offset(100.0, '10') == 110.0


def test_map_slave_uses_metric_and_offset():
    cfg = {'METRIC': 'WATER', 'OFFSET': 849.503}
    assert mbus_mapper.map_slave(cfg, 100.0) == {'WATER': 949.503}


def test_map_slave_defaults_metric_water():
    assert mbus_mapper.map_slave({}, 7.0) == {'WATER': 7.0}


def test_map_to_topics_builds_per_slave_topic():
    data = {16: {'WATER': 949.503}}
    topics = mbus_mapper.map_to_topics(data, 'PLANT/MBUS')
    assert len(topics) == 1
    topic, payload = topics[0]
    assert topic == 'PLANT/MBUS/16'
    assert json.loads(payload) == {'WATER': 949.503}


def test_map_to_topics_empty():
    assert mbus_mapper.map_to_topics({}, 'PLANT/MBUS') == []
