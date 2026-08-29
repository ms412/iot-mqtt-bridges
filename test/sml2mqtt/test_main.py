#!/usr/bin/env python3
"""Tests for the Sml2Mqtt bridge orchestration with reader and MQTT mocked."""

import json

from sml2mqtt.main import Sml2Mqtt


def _bridge_with_mocks(mocker):
    bridge = Sml2Mqtt('sml2mqtt/config/sml2mqtt.yaml')
    bridge._config = {'BROKER': {'PUBLISH': 'HOME/SML'}}
    bridge._log = mocker.MagicMock()
    bridge._mqtt = mocker.MagicMock()
    bridge._reader = mocker.MagicMock()
    return bridge


def test_read_data_parses_frame(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._reader.read_frame.return_value = b'rawframe'
    parse = mocker.patch(
        'sml2mqtt.main.sml_mapper.parse_frame',
        return_value={'1.8.0': {'data_value': 1}},
    )
    data = bridge.read_data()
    parse.assert_called_once_with(b'rawframe')
    assert data == {'1.8.0': {'data_value': 1}}


def test_read_data_none_frame_returns_empty(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._reader.read_frame.return_value = None
    assert bridge.read_data() == {}


def test_map_to_topics_single_topic(mocker):
    bridge = _bridge_with_mocks(mocker)
    store = {'1.8.0': {'data_value': 1, 'data_unit': 'Wh', 'data_type': None}}
    topics = bridge.map_to_topics(store)
    assert topics[0][0] == 'HOME/SML'
    decoded = json.loads(topics[0][1])
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == store


def test_publish_data_calls_mqtt(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge.publish_data([('HOME/SML', '{"x": 1}')])
    bridge._mqtt.publish.assert_called_once_with('HOME/SML', '{"x": 1}')


def test_stop_releases_resources(mocker):
    bridge = _bridge_with_mocks(mocker)
    bridge._running = True
    bridge.stop()
    assert bridge._running is False
    bridge._reader.close.assert_called_once()
    bridge._mqtt.disconnect.assert_called_once()
