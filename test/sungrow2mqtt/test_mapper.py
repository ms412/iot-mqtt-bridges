#!/usr/bin/env python3
"""Unit tests for sungrow2mqtt.sungrow_mapper (pure transformation functions)."""

import json

from sungrow2mqtt import sungrow_mapper


def test_flatten_measurements_real_with_unit():
    items = [
        {'data_name': 'Total Power', 'data_value': 4200, 'data_unit': 'W'},
        {'data_name': 'Daily Yield', 'data_value': 12.5, 'data_unit': 'kWh'},
    ]
    flat = sungrow_mapper.flatten_measurements(items)
    assert flat == {
        'Total Power': {'value': 4200, 'unit': 'W'},
        'Daily Yield': {'value': 12.5, 'unit': 'kWh'},
    }


def test_flatten_measurements_without_unit():
    items = [{'data_name': 'Status', 'data_value': 'Run'}]
    flat = sungrow_mapper.flatten_measurements(items)
    assert flat == {'Status': 'Run'}


def test_flatten_measurements_skips_unnamed_and_non_dict():
    items = [{'data_value': 5}, 'garbage', {'data_name': 'Ok', 'data_value': 1}]
    flat = sungrow_mapper.flatten_measurements(items)
    assert flat == {'Ok': 1}


def test_process_device_merges_real_and_direct_with_metadata():
    device = {
        'dev_id': 1,
        'dev_name': 'Inverter',
        'dev_model': 'SH10RT',
        'REAL': [{'data_name': 'Power', 'data_value': 4200, 'data_unit': 'W'}],
        'DIRECT': [{'data_name': 'MPPT1', 'data_value': 300, 'data_unit': 'V'}],
    }
    payload = sungrow_mapper.process_device(device)
    assert payload['dev_name'] == 'Inverter'
    assert payload['dev_model'] == 'SH10RT'
    assert payload['Power'] == {'value': 4200, 'unit': 'W'}
    assert payload['MPPT1'] == {'value': 300, 'unit': 'V'}


def test_build_payload_includes_epoch_timestamp():
    import time

    before = int(time.time())
    payload = json.loads(sungrow_mapper.build_payload({'Power': 4200}))
    after = int(time.time())

    assert 'timestamp' in payload
    assert isinstance(payload['timestamp'], int)
    assert before <= payload['timestamp'] <= after
    assert payload['Power'] == 4200


def test_build_payload_does_not_mutate_input():
    original = {'Power': 4200}
    sungrow_mapper.build_payload(original)
    assert 'timestamp' not in original


def test_map_to_topics_builds_per_device_topic():
    devices = [{
        'dev_id': 1,
        'dev_name': 'Inverter',
        'REAL': [{'data_name': 'Power', 'data_value': 4200, 'data_unit': 'W'}],
        'DIRECT': [],
    }]
    topics = sungrow_mapper.map_to_topics(devices, 'HOME/SUNGROW')
    assert len(topics) == 1
    topic, payload = topics[0]
    assert topic == 'HOME/SUNGROW/1'
    decoded = json.loads(payload)
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == {'dev_name': 'Inverter', 'Power': {'value': 4200, 'unit': 'W'}}


def test_map_to_topics_skips_devices_without_id():
    devices = [{'dev_name': 'NoId', 'REAL': [], 'DIRECT': []}]
    assert sungrow_mapper.map_to_topics(devices, 'HOME/SUNGROW') == []
