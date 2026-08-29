#!/usr/bin/env python3
"""Tests for the So2Mqtt bridge orchestration with reader and MQTT mocked."""

import json

from so2mqtt.main import So2Mqtt


def _bridge_with_mocks(mocker):
    bridge = So2Mqtt('so2mqtt/config/so2mqtt.yaml')
    bridge._config = {'BROKER': {'PUBLISH': 'HOME/S0'}}
    bridge._log = mocker.MagicMock()
    bridge._mqtt = mocker.MagicMock()
    bridge._reader = mocker.MagicMock()
    return bridge


def test_read_data_processes_each_interface(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._reader.read_all.return_value = {'SERIAL01': ['h', '5000', '300']}
    bridge._reader.interface_config.return_value = {
        'PORT': '/dev/ttyUSB1',
        'GAS01': {'BYTE': 1, 'FACTOR': 100, 'OFFSET': 2158},
    }
    data = bridge.read_data()
    assert data == {'SERIAL01': {'GAS01': {'S0': 2208.0, 'S0_raw': '5000'}}}


def test_map_to_topics_nested(mocker):
    bridge = _bridge_with_mocks(mocker)
    data = {'SERIAL01': {'GAS01': {'S0': 2208.0, 'S0_raw': '5000'}}}
    topics = bridge.map_to_topics(data)
    assert topics[0][0] == 'HOME/S0/SERIAL01/GAS01'
    decoded = json.loads(topics[0][1])
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == {'S0': 2208.0, 'S0_raw': '5000'}


def test_publish_data_is_retained(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge.publish_data([('HOME/S0/SERIAL01/GAS01', '{"S0": 1}')])
    bridge._mqtt.publish.assert_called_once_with(
        'HOME/S0/SERIAL01/GAS01', '{"S0": 1}', retain=True
    )


def test_stop_releases_resources(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._running = True
    bridge.stop()
    assert bridge._running is False
    bridge._reader.close.assert_called_once()
    bridge._mqtt.disconnect.assert_called_once()
