#!/usr/bin/env python3
"""Tests for sml2mqtt.sml_mapper with smllib mocked."""

import json

from smllib.errors import CrcError

from sml2mqtt import sml_mapper


class _Obis(str):
    """An OBIS identifier string that also carries an obis_short attribute.

    parse_frame keys the store by entry.obis.obis_short and looks up the label
    via OBIS_NAMES.get(entry.obis); subclassing str keeps the dict lookup working.
    """

    @property
    def obis_short(self) -> str:
        return self._short

    @classmethod
    def make(cls, value: str, short: str) -> "_Obis":
        obj = cls(value)
        obj._short = short
        return obj


def test_parse_frame_builds_store(mocker):
    entry = mocker.MagicMock()
    entry.obis = _Obis.make('0100010800ff', '1.8.0')
    entry.get_value.return_value = 12345
    entry.unit = 30  # Wh

    frame = mocker.MagicMock()
    frame.get_obis.return_value = [entry]

    stream = mocker.MagicMock()
    stream.get_frame.return_value = frame
    mocker.patch('sml2mqtt.sml_mapper.SmlStreamReader', return_value=stream)

    store = sml_mapper.parse_frame(b'rawframe')
    assert store['1.8.0']['data_value'] == 12345
    assert store['1.8.0']['data_unit'] == 'Wh'
    assert store['1.8.0']['data_type'] == 'Z\u00e4hlerstand Total'


def test_parse_frame_none_returns_empty(mocker):
    stream = mocker.MagicMock()
    stream.get_frame.return_value = None
    mocker.patch('sml2mqtt.sml_mapper.SmlStreamReader', return_value=stream)

    assert sml_mapper.parse_frame(b'x') == {}


def test_parse_frame_handles_smllib_exception(mocker):
    stream = mocker.MagicMock()
    stream.get_frame.side_effect = CrcError(b'msg', 1, 2)
    mocker.patch('sml2mqtt.sml_mapper.SmlStreamReader', return_value=stream)

    # Must not raise; returns an empty store.
    assert sml_mapper.parse_frame(b'x') == {}


def test_map_to_topics_single_topic():
    store = {'1.8.0': {'data_value': 1, 'data_unit': 'Wh', 'data_type': None}}
    topics = sml_mapper.map_to_topics(store, 'HOME/SML')
    assert len(topics) == 1
    assert topics[0][0] == 'HOME/SML'
    decoded = json.loads(topics[0][1])
    assert isinstance(decoded.pop('timestamp'), int)
    assert decoded == store


def test_map_to_topics_empty_store():
    assert sml_mapper.map_to_topics({}, 'HOME/SML') == []
