#!/usr/bin/env python3
"""Tests for the Mbus2Mqtt bridge orchestration with reader and MQTT mocked."""

import json

from mbus2mqtt.main import Mbus2Mqtt


def _bridge_with_mocks(mocker):
    bridge = Mbus2Mqtt('mbus2mqtt/config/mbus2mqtt.yaml')
    bridge._config = {'BROKER': {'PUBLISH': 'PLANT/MBUS'}}
    bridge._log = mocker.MagicMock()
    bridge._mqtt = mocker.MagicMock()
    bridge._reader = mocker.MagicMock()
    return bridge


def test_read_data_maps_each_slave(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._reader.read_all.return_value = {16: 100.0}
    bridge._reader.slave_config.return_value = {'METRIC': 'WATER', 'OFFSET': 849.503}

    data = bridge.read_data()
    assert data == {16: {'WATER': 949.503}}


def test_map_to_topics_uses_publish_base(mocker):
    bridge = _bridge_with_mocks(mocker)
    topics = bridge.map_to_topics({16: {'WATER': 949.503}})
    assert topics[0][0] == 'PLANT/MBUS/16'
    assert json.loads(topics[0][1]) == {'WATER': 949.503}


def test_publish_data_calls_mqtt(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge.publish_data([('PLANT/MBUS/16', '{"WATER": 1}')])
    bridge._mqtt.publish.assert_called_once_with('PLANT/MBUS/16', '{"WATER": 1}')


def test_stop_releases_resources(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._running = True
    bridge.stop()
    assert bridge._running is False
    bridge._reader.close.assert_called_once()
    bridge._mqtt.disconnect.assert_called_once()
