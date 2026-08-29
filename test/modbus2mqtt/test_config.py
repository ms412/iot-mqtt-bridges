#!/usr/bin/env python3
"""Tests for BaseConfig device-file resolution using the real modbus2mqtt configs."""

from common.config.base_config import BaseConfig


def test_waterlevel_config_resolves_file_and_query():
    cfg = BaseConfig.load('modbus2mqtt/config/modbus2mqtt_waterlevel.yaml').data
    device = cfg['MODBUS'][1]
    # FILE reference is replaced by a resolved REGISTERS list.
    assert 'FILE' not in device
    # QUERY narrows the register list to the named registers only.
    assert [reg['Name'] for reg in device['REGISTERS']] == ['WATER_LEVEL']


def test_photovoltaic_config_loads_full_register_lists():
    cfg = BaseConfig.load('modbus2mqtt/config/modbus2mqtt_photovoltaic.yaml').data
    modbus = cfg['MODBUS']
    # Devices 3 and 9 are active in the photovoltaic config.
    assert set(k for k in modbus if isinstance(k, int)) == {3, 9}
    # SDM120 (device 9) has its full 8-register definition.
    assert len(modbus[9]['REGISTERS']) == 8


def test_filter_registers_allowlist():
    cfg = BaseConfig('modbus2mqtt/config/modbus2mqtt_waterlevel.yaml')
    registers = [{'Name': 'A'}, {'Name': 'B'}, {'Name': 'C'}]
    filtered = cfg._filter_registers(registers, ['A', 'C'])
    assert [r['Name'] for r in filtered] == ['A', 'C']


def test_filter_registers_none_keeps_all():
    cfg = BaseConfig('modbus2mqtt/config/modbus2mqtt_waterlevel.yaml')
    registers = [{'Name': 'A'}, {'Name': 'B'}]
    assert cfg._filter_registers(registers, None) == registers
