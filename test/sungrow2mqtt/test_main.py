#!/usr/bin/env python3
"""Tests for the Sungrow2Mqtt bridge orchestration with reader and MQTT mocked."""

import json

from sungrow2mqtt.main import Sungrow2Mqtt, _resolve_env


def _bridge_with_mocks(mocker):
    bridge = Sungrow2Mqtt('sungrow2mqtt/config/sungrow2mqtt.yaml')
    bridge._config = {'BROKER': {'PUBLISH': 'HOME/SUNGROW'}}
    bridge._log = mocker.MagicMock()
    bridge._mqtt = mocker.MagicMock()
    bridge._reader = mocker.MagicMock()
    return bridge


def test_resolve_env_reads_from_environment(monkeypatch):
    monkeypatch.setenv('SUNGROW_PASSWORD', 'topsecret')
    assert _resolve_env('${SUNGROW_PASSWORD}') == 'topsecret'


def test_resolve_env_passes_through_plain_values():
    assert _resolve_env('user') == 'user'
    assert _resolve_env(443) == 443


def test_resolve_env_missing_var_becomes_empty(monkeypatch):
    monkeypatch.delenv('SUNGROW_MISSING', raising=False)
    assert _resolve_env('${SUNGROW_MISSING}') == ''


def test_read_data_delegates_to_reader(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._reader.read_all.return_value = [{'dev_id': 1}]
    assert bridge.read_data() == [{'dev_id': 1}]


def test_map_to_topics_uses_publish_base(mocker):
    bridge = _bridge_with_mocks(mocker)
    devices = [{
        'dev_id': 1,
        'REAL': [{'data_name': 'Power', 'data_value': 4200, 'data_unit': 'W'}],
        'DIRECT': [],
    }]
    topics = bridge.map_to_topics(devices)
    assert topics[0][0] == 'HOME/SUNGROW/1'
    decoded = json.loads(topics[0][1])
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == {'Power': {'value': 4200, 'unit': 'W'}}


def test_publish_data_calls_mqtt(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge.publish_data([('HOME/SUNGROW/1', '{"x": 1}')])
    bridge._mqtt.publish.assert_called_once_with('HOME/SUNGROW/1', '{"x": 1}')


def test_stop_releases_resources(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._running = True
    bridge.stop()
    assert bridge._running is False
    bridge._reader.close.assert_called_once()
    bridge._mqtt.disconnect.assert_called_once()
