#!/usr/bin/env python3
"""Tests for SungrowReader with the WebSocket connection mocked."""

import json

import pytest

from sungrow2mqtt.sungrow_reader import SungrowReader

SUNGROW_CFG = {
    'HOST': '192.168.2.81',
    'PORT': 443,
    'USERNAME': 'user',
    'PASSWORD': 'secret',
    'LANG': 'en_us',
    'TIMEOUT': 5,
}


@pytest.fixture(autouse=True)
def _no_sleep(mocker):
    # _receive_json sleeps 1s per call; skip it to keep tests fast.
    mocker.patch('sungrow2mqtt.sungrow_reader.time.sleep')


def _ws_with_responses(mocker, responses):
    """Return a fake websocket whose recv() yields the given JSON responses."""
    fake_ws = mocker.MagicMock()
    fake_ws.recv.side_effect = [json.dumps(r) for r in responses]
    mocker.patch(
        'sungrow2mqtt.sungrow_reader.websocket.create_connection',
        return_value=fake_ws,
    )
    return fake_ws


def test_connect_authenticates_and_captures_token(mocker):
    fake_ws = _ws_with_responses(mocker, [
        {'result_code': 1, 'token': 'tok0'},                              # connect
        {'result_code': 1, 'result_data': {'token': 'tok1'}},             # login
    ])
    reader = SungrowReader(SUNGROW_CFG)
    reader.connect()

    assert reader._token == 'tok1'
    # A connect and a login message were sent.
    assert fake_ws.send.call_count == 2
    login = json.loads(fake_ws.send.call_args_list[1].args[0])
    assert login['service'] == 'login'
    assert login['username'] == 'user'
    assert login['passwd'] == 'secret'


def test_read_all_attaches_real_and_direct(mocker):
    _ws_with_responses(mocker, [
        {'result_code': 1, 'token': 'tok0'},                              # connect
        {'result_code': 1, 'result_data': {'token': 'tok1'}},             # login
        {'result_code': 1, 'result_data': {'list': [{'dev_id': 1}]}},     # devicelist
        {'result_code': 1, 'result_data': {'list': [{'data_name': 'P'}]}},  # real
        {'result_code': 1, 'result_data': {'list': [{'data_name': 'V'}]}},  # direct
    ])
    reader = SungrowReader(SUNGROW_CFG)
    reader.connect()
    devices = reader.read_all()

    assert len(devices) == 1
    assert devices[0]['dev_id'] == 1
    assert devices[0]['REAL'] == [{'data_name': 'P'}]
    assert devices[0]['DIRECT'] == [{'data_name': 'V'}]


def test_read_all_returns_empty_on_failed_devicelist(mocker):
    _ws_with_responses(mocker, [
        {'result_code': 1, 'token': 'tok0'},                  # connect
        {'result_code': 1, 'result_data': {'token': 't'}},    # login
        {'result_code': 0},                                   # devicelist failure
    ])
    reader = SungrowReader(SUNGROW_CFG)
    reader.connect()
    assert reader.read_all() == []


def test_ping_true_on_ack(mocker):
    _ws_with_responses(mocker, [
        {'result_code': 1, 'token': 'tok0'},
        {'result_code': 1, 'result_data': {'token': 't'}},
        {'result_code': 1},   # ping ack
    ])
    reader = SungrowReader(SUNGROW_CFG)
    reader.connect()
    assert reader.ping() is True


def test_close_is_safe_without_connection(mocker):
    reader = SungrowReader(SUNGROW_CFG)
    reader.close()  # must not raise even though _ws is None
    assert reader._ws is None
