#!/usr/bin/env python3
"""M-Bus serial I/O for the mbus2mqtt bridge (via pyMeterBus)."""

import json
import logging

import meterbus
import serial
from meterbus.exceptions import MBusError

__APP__ = "mbus2mqtt"

# Non-device keys that live alongside slave-address entries in the MBUS section.
_TRANSPORT_KEYS = {
    "DEVICE",
    "BAUDRATE",
    "UPDATE_INTERVAL",
    "STARTUP_DELAY",
}


class MbusReader:
    """Own the M-Bus serial interface and read raw values per slave."""

    def __init__(self, mbus_config: dict) -> None:
        """Initialize the reader.

        Args:
            mbus_config: The MBUS section of the bridge config.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{__APP__}.{_lib_name}.{self.__class__.__name__}")

        self._config = mbus_config or {}
        self._if = None

    def _slaves(self) -> dict:
        """Return the configured M-Bus slave-address entries.

        Returns:
            Mapping of slave id (int) to its config dict.
        """
        slaves: dict = {}
        for key, value in self._config.items():
            if key in _TRANSPORT_KEYS:
                continue
            if isinstance(value, dict):
                slaves[int(key)] = value
        return slaves

    def connect(self) -> None:
        """Open the M-Bus serial interface (8E1, 0.5s timeout).

        Returns:
            None.
        """
        device = str(self._config.get("DEVICE", "/dev/ttyUSB0"))
        baudrate = int(self._config.get("BAUDRATE", 2400))

        self._if = serial.Serial(device, baudrate, 8, "E", 1, 0.5)
        self._if.flush()
        self._log.info(
            "M-Bus serial opened on %s (%d slave(s) configured)", device, len(self._slaves())
        )

    def _read_value(self, slave_id: int) -> object:
        """Read the primary record value from one slave via meterbus.

        Args:
            slave_id: The M-Bus slave address.

        Returns:
            The primary record's value.
        """
        meterbus.send_ping_frame(self._if, slave_id)
        ack = meterbus.load(meterbus.recv_frame(self._if, slave_id))
        assert isinstance(ack, meterbus.TelegramACK)

        meterbus.send_request_frame(self._if, slave_id)
        frame = meterbus.load(meterbus.recv_frame(self._if, meterbus.FRAME_DATA_LENGTH))
        assert isinstance(frame, meterbus.TelegramLong)

        json_data = json.loads(frame.to_JSON())
        return json_data["body"]["records"][0]["value"]

    def read_slave(self, slave_id: int) -> object:
        """Read a single slave, returning its raw value or None on failure.

        Args:
            slave_id: The M-Bus slave address.

        Returns:
            The raw value, or None if the read failed.
        """
        try:
            return self._read_value(slave_id)
        except (
            AssertionError,
            MBusError,
            serial.SerialException,
            KeyError,
            IndexError,
            ValueError,
        ) as exc:
            self._log.error("Failed to read MBus slave id=%s: %s", slave_id, exc)
            return None

    def read_all(self) -> dict:
        """Read every configured slave.

        Returns:
            Mapping of slave id to raw value; failed reads are omitted.
        """
        data: dict = {}
        for slave_id in self._slaves():
            self._log.debug("Reading MBus slave id=%s", slave_id)
            value = self.read_slave(slave_id)
            if value is None:
                continue
            data[slave_id] = value
        return data

    def slave_config(self, slave_id: int) -> dict:
        """Return the config dict for a slave address.

        Args:
            slave_id: The M-Bus slave address.

        Returns:
            The slave's config dict, or an empty dict if unknown.
        """
        return self._slaves().get(slave_id, {})

    def close(self) -> None:
        """Close the serial interface if it is open.

        Returns:
            None.
        """
        try:
            self._if.close()
        except AttributeError:
            self._log.debug("No open serial interface to close")
