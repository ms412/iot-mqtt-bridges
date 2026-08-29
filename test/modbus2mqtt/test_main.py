#!/usr/bin/env python3
"""Tests for the Modbus2Mqtt bridge orchestration with reader and MQTT mocked."""

import json

from modbus2mqtt.main import Modbus2Mqtt


def _bridge_with_mocks(mocker):
    bridge = Modbus2Mqtt('modbus2mqtt/config/modbus2mqtt_photovoltaic.yaml')
    bridge._config = {'BROKER': {'PUBLISH': 'PLANT/PV'}}
    bridge._log = mocker.MagicMock()
    bridge._mqtt = mocker.MagicMock()
    bridge._reader = mocker.MagicMock()
    return bridge


def test_read_data_processes_each_device(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._reader.read_all.return_value = {9: {'VOLTAGE': 230}}
    bridge._reader.registers_for.return_value = [
        {'Name': 'VOLTAGE', 'Scale Factor': 1, 'Unit': 'V'}
    ]

    data = bridge.read_data()
    assert data == {9: {'VOLTAGE': {'VALUE': 230.0, 'UNIT': 'V'}}}


def test_map_to_topics_uses_publish_base(mocker):
    bridge = _bridge_with_mocks(mocker)
    topics = bridge.map_to_topics({9: {'VOLTAGE': {'VALUE': 230.0, 'UNIT': 'V'}}})
    assert topics[0][0] == 'PLANT/PV/9'
    decoded = json.loads(topics[0][1])
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == {'VOLTAGE': {'VALUE': 230.0, 'UNIT': 'V'}}


def test_publish_data_calls_mqtt_publish(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge.publish_data([('PLANT/PV/9', '{"x": 1}')])
    bridge._mqtt.publish.assert_called_once_with('PLANT/PV/9', '{"x": 1}')


def test_stop_closes_reader_and_disconnects(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._running = True
    bridge.stop()
    assert bridge._running is False
    bridge._reader.close.assert_called_once()
    bridge._mqtt.disconnect.assert_called_once()
