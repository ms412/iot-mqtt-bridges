#!/usr/bin/env python3
"""Modbus protocol I/O for the modbus2mqtt bridge.

Handles connecting to Modbus devices and reading raw register values only; no
MQTT logic. One :class:`Modbus` client is created per configured slave id.
"""

import logging

from modbus2mqtt.modbus import Modbus

__APP__ = "modbus2mqtt"

# Non-device keys that live alongside slave entries in the MODBUS config section.
_TRANSPORT_KEYS = {
    "INTERFACE",
    "HOST",
    "PORT",
    "BAUDRATE",
    "UPDATE_INTERVAL",
    "STARTUP_DELAY",
}


class ModbusReader:
    """Own Modbus connections and raw register reads for all devices."""

    def __init__(self, modbus_config: dict) -> None:
        """Initialize the reader.

        Args:
            modbus_config: The MODBUS section of the bridge config, containing
                transport settings and one entry per slave id.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{__APP__}.{_lib_name}.{self.__class__.__name__}")

        self._config = modbus_config or {}
        self._clients: dict = {}
        self._registers: dict = {}

    def _devices(self) -> dict:
        """Return the slave entries that carry a ``REGISTERS`` list.

        Returns:
            Mapping of device id to its resolved device config.
        """
        devices: dict = {}
        for device_id, value in self._config.items():
            if device_id in _TRANSPORT_KEYS:
                continue
            if isinstance(value, dict) and value.get("REGISTERS"):
                devices[device_id] = value
        return devices

    def connect(self) -> None:
        """Create and connect a :class:`Modbus` client for every device.

        Returns:
            None.
        """
        interface = str(self._config.get("INTERFACE", "serial"))
        host = str(self._config.get("HOST", "/dev/ttyUSB0"))
        port = self._config.get("PORT", host if interface == "serial" else 502)
        baudrate = int(self._config.get("BAUDRATE", 9600))

        for device_id, device in self._devices().items():
            client = Modbus(device_id)
            client.connect(interface, host=host, port=port, baudrate=baudrate)
            self._clients[device_id] = client
            self._registers[device_id] = device["REGISTERS"]
            self._log.debug("Modbus client initialized for device %s", device_id)

        self._log.info("Connected %d Modbus device(s) via %s", len(self._clients), interface)

    def _function_code(self, register: dict) -> str:
        """Return the primary function code for a register.

        Args:
            register: A register definition; ``Function Codes`` may list more
                than one code (e.g. ``"0x03, 0x06"``).

        Returns:
            The first function code as a string (e.g. ``"0x03"``).
        """
        raw = str(register.get("Function Codes", "")).strip()
        return raw.split(",")[0].strip()

    def read_device(self, device_id: int, registers: list[dict]) -> dict:
        """Read every register for a single device.

        Args:
            device_id: The Modbus slave id.
            registers: Register definitions for this device.

        Returns:
            Mapping of register name to raw value; failed reads are omitted.
        """
        client = self._clients[device_id]
        readings: dict = {}
        for register in registers:
            value = client.get_data(
                self._function_code(register),
                address=register.get("Start"),
                size=register.get("Size"),
                datatype=register.get("Data Type"),
            )
            if value is None:
                self._log.error(
                    "No data for register %s on device %s", register.get("Name"), device_id
                )
                continue
            readings[register.get("Name")] = value
        return readings

    def read_all(self) -> dict:
        """Read every register for every connected device.

        Returns:
            Mapping of device id to a dict of register name -> raw value.
        """
        data: dict = {}
        for device_id, registers in self._registers.items():
            data[device_id] = self.read_device(device_id, registers)
        return data

    def registers_for(self, device_id: int) -> list[dict]:
        """Return the cached register definitions for a device.

        Args:
            device_id: The Modbus slave id.

        Returns:
            The register definitions, or an empty list if unknown.
        """
        return self._registers.get(device_id, [])

    def close(self) -> None:
        """Close all open Modbus client connections.

        Returns:
            None.
        """
        for device_id, client in self._clients.items():
            try:
                client._client.close()
            except AttributeError:
                self._log.debug("No open client to close for device %s", device_id)
