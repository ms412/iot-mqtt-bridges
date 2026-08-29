#!/usr/bin/env python3
"""Tests for MbusReader with meterbus and serial mocked."""

import json

from mbus2mqtt.mbus_reader import MbusReader

MBUS_CFG = {
    'DEVICE': '/dev/ttyUSB0',
    'BAUDRATE': 2400,
    'UPDATE_INTERVAL': 30,
    'STARTUP_DELAY': 5,
    16: {'METRIC': 'WATER', 'OFFSET': 849.503},
}


def test_slaves_excludes_transport_keys():
    reader = MbusReader(MBUS_CFG)
    assert set(reader._slaves().keys()) == {16}


def test_slave_config_lookup():
    reader = MbusReader(MBUS_CFG)
    assert reader.slave_config(16) == {'METRIC': 'WATER', 'OFFSET': 849.503}


def test_connect_opens_serial(mocker):
    serial_ctor = mocker.patch('mbus2mqtt.mbus_reader.serial.Serial')
    reader = MbusReader(MBUS_CFG)
    reader.connect()
    serial_ctor.assert_called_once()


def test_read_slave_returns_primary_record_value(mocker):
    meterbus = mocker.patch('mbus2mqtt.mbus_reader.meterbus')

    ack = mocker.MagicMock()
    long_frame = mocker.MagicMock()
    long_frame.to_JSON.return_value = json.dumps(
        {'body': {'records': [{'value': 123.4}]}}
    )
    # load() is called twice: first returns ACK, then the long telegram.
    meterbus.load.side_effect = [ack, long_frame]
    meterbus.TelegramACK = type(ack)
    meterbus.TelegramLong = type(long_frame)

    mocker.patch('mbus2mqtt.mbus_reader.serial.Serial')
    reader = MbusReader(MBUS_CFG)
    reader.connect()

    value = reader.read_slave(16)
    assert value == 123.4


def test_read_slave_returns_none_on_error(mocker):
    meterbus = mocker.patch('mbus2mqtt.mbus_reader.meterbus')
    meterbus.load.side_effect = AssertionError('bad frame')
    meterbus.TelegramACK = type('A', (), {})
    meterbus.TelegramLong = type('L', (), {})

    mocker.patch('mbus2mqtt.mbus_reader.serial.Serial')
    reader = MbusReader(MBUS_CFG)
    reader.connect()

    assert reader.read_slave(16) is None


def test_read_slave_returns_none_on_mbus_error(mocker):
    # A transient empty/bad frame raises meterbus MBusError; it must be caught
    # and returned as None (a skipped read), not propagated to crash the loop.
    from meterbus.exceptions import MBusFrameDecodeError

    meterbus = mocker.patch('mbus2mqtt.mbus_reader.meterbus')
    meterbus.load.side_effect = MBusFrameDecodeError('empty frame', None)
    meterbus.TelegramACK = type('A', (), {})
    meterbus.TelegramLong = type('L', (), {})

    mocker.patch('mbus2mqtt.mbus_reader.serial.Serial')
    reader = MbusReader(MBUS_CFG)
    reader.connect()

    assert reader.read_slave(16) is None


def test_read_all_skips_failed_slave(mocker):
    # read_all must continue and simply omit a slave whose read raised.
    from meterbus.exceptions import MBusFrameDecodeError

    meterbus = mocker.patch('mbus2mqtt.mbus_reader.meterbus')
    meterbus.load.side_effect = MBusFrameDecodeError('empty frame', None)
    meterbus.TelegramACK = type('A', (), {})
    meterbus.TelegramLong = type('L', (), {})

    mocker.patch('mbus2mqtt.mbus_reader.serial.Serial')
    reader = MbusReader(MBUS_CFG)
    reader.connect()

    assert reader.read_all() == {}
