#!/usr/bin/env python3
"""Tests for ModbusReader with the underlying Modbus client mocked."""

from modbus2mqtt.modbus_reader import ModbusReader

MODBUS_CFG = {
    'INTERFACE': 'serial',
    'HOST': '/dev/ttyUSB0',
    'BAUDRATE': 9600,
    'UPDATE_INTERVAL': 10,
    'STARTUP_DELAY': 5,
    9: {
        'REGISTERS': [
            {'Name': 'VOLTAGE', 'Function Codes': '0x04', 'Start': 0, 'Size': 2, 'Data Type': 'float32'},
            {'Name': 'CURRENT', 'Function Codes': '0x04', 'Start': 6, 'Size': 2, 'Data Type': 'float32'},
        ]
    },
}


def test_devices_excludes_transport_keys():
    reader = ModbusReader(MODBUS_CFG)
    assert set(reader._devices().keys()) == {9}


def test_function_code_takes_first():
    reader = ModbusReader(MODBUS_CFG)
    assert reader._function_code({'Function Codes': '0x03, 0x06'}) == '0x03'
    assert reader._function_code({'Function Codes': '0x04'}) == '0x04'


def test_connect_builds_one_client_per_device(mocker):
    fake_client = mocker.MagicMock()
    modbus_cls = mocker.patch('modbus2mqtt.modbus_reader.Modbus', return_value=fake_client)

    reader = ModbusReader(MODBUS_CFG)
    reader.connect()

    modbus_cls.assert_called_once_with(9)
    fake_client.connect.assert_called_once()
    assert reader.registers_for(9)[0]['Name'] == 'VOLTAGE'


def test_read_device_collects_values_and_skips_none(mocker):
    fake_client = mocker.MagicMock()
    fake_client.get_data.side_effect = [230.0, None]
    mocker.patch('modbus2mqtt.modbus_reader.Modbus', return_value=fake_client)

    reader = ModbusReader(MODBUS_CFG)
    reader.connect()
    readings = reader.read_device(9, MODBUS_CFG[9]['REGISTERS'])

    # CURRENT returned None and must be skipped.
    assert readings == {'VOLTAGE': 230.0}


def test_read_all_maps_by_device(mocker):
    fake_client = mocker.MagicMock()
    fake_client.get_data.return_value = 1.0
    mocker.patch('modbus2mqtt.modbus_reader.Modbus', return_value=fake_client)

    reader = ModbusReader(MODBUS_CFG)
    reader.connect()
    data = reader.read_all()

    assert set(data.keys()) == {9}
    assert data[9] == {'VOLTAGE': 1.0, 'CURRENT': 1.0}
