#!/usr/bin/env python3
"""Tests for So0Reader with serial mocked."""

from so2mqtt.so_reader import So0Reader

S0_CFG = {
    'UPDATE_INTERVAL': 15,
    'STARTUP_DELAY': 5,
    'SERIAL01': {
        'PORT': '/dev/ttyUSB1',
        'BAUDRATE': 38400,
        'GAS01': {'BYTE': 1, 'FACTOR': 100, 'OFFSET': 2158},
    },
}


def test_interfaces_excludes_transport_keys():
    reader = So0Reader(S0_CFG)
    assert set(reader._interfaces().keys()) == {'SERIAL01'}


def test_interface_config_lookup():
    reader = So0Reader(S0_CFG)
    assert reader.interface_config('SERIAL01')['PORT'] == '/dev/ttyUSB1'


def test_connect_opens_one_port_per_interface(mocker):
    serial_ctor = mocker.patch('so2mqtt.so_reader.serial.Serial')
    reader = So0Reader(S0_CFG)
    reader.connect()
    serial_ctor.assert_called_once()


def test_query_interface_splits_response(mocker):
    fake_serial = mocker.MagicMock()
    fake_serial.readline.return_value = b'header;5000;300;trailer'
    mocker.patch('so2mqtt.so_reader.serial.Serial', return_value=fake_serial)
    mocker.patch('so2mqtt.so_reader.time.sleep')  # skip the 1s wait

    reader = So0Reader(S0_CFG)
    reader.connect()
    fields = reader.query_interface('SERIAL01')

    fake_serial.write.assert_called_once()
    assert fields == ['header', '5000', '300', 'trailer']


def test_read_all_maps_by_interface(mocker):
    fake_serial = mocker.MagicMock()
    fake_serial.readline.return_value = b'h;5000;300'
    mocker.patch('so2mqtt.so_reader.serial.Serial', return_value=fake_serial)
    mocker.patch('so2mqtt.so_reader.time.sleep')

    reader = So0Reader(S0_CFG)
    reader.connect()
    data = reader.read_all()

    assert set(data.keys()) == {'SERIAL01'}
    assert data['SERIAL01'] == ['h', '5000', '300']
