#!/usr/bin/env python3
"""S0-USB serial I/O for the so2mqtt bridge."""

import logging
import time

import serial

__APP__ = "so2mqtt"

# Non-interface keys that live alongside the interface entries in the S0 section.
_TRANSPORT_KEYS = {
    "UPDATE_INTERVAL",
    "STARTUP_DELAY",
}

# Query command written to the S0-USB adapter to request a reading.
_QUERY = b"$?\n"


class So0Reader:
    """Own the S0-USB serial interfaces and read raw field lists per interface."""

    def __init__(self, s0_config: dict) -> None:
        """Initialize the reader.

        Args:
            s0_config: The S0 section of the bridge config.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{__APP__}.{_lib_name}.{self.__class__.__name__}")

        self._config = s0_config or {}
        self._ports: dict = {}

    def _interfaces(self) -> dict:
        """Return the configured serial-interface entries.

        Returns:
            Mapping of interface name to its config dict (those with a ``PORT``).
        """
        interfaces: dict = {}
        for name, value in self._config.items():
            if name in _TRANSPORT_KEYS:
                continue
            if isinstance(value, dict) and "PORT" in value:
                interfaces[name] = value
        return interfaces

    def connect(self) -> None:
        """Open a serial port for every configured S0 interface.

        Returns:
            None.
        """
        for name, interface in self._interfaces().items():
            port = str(interface.get("PORT", "/dev/ttyUSB0"))
            baudrate = int(interface.get("BAUDRATE", 38400))
            handle = serial.Serial(port, baudrate, timeout=3.0)
            handle.flush()
            self._ports[name] = handle
            self._log.debug("Serial port opened: interface=%s, port=%s", name, port)

        self._log.info("Opened %d S0 interface(s)", len(self._ports))

    def query_interface(self, name: str) -> list[str]:
        """Query one interface and return its ``;``-separated field list.

        Args:
            name: The interface name.

        Returns:
            The response split on ``;``.
        """
        handle = self._ports[name]
        written = handle.write(_QUERY)
        time.sleep(1)
        self._log.debug("Wrote %s bytes to interface %s", written, name)

        line = handle.readline().decode("ASCII")
        self._log.debug("Received data from %s: %s", name, line)
        return line.split(";")

    def read_all(self) -> dict:
        """Query every interface.

        Returns:
            Mapping of interface name to its field list; failed reads are omitted.
        """
        data: dict = {}
        for name in self._ports:
            try:
                data[name] = self.query_interface(name)
            except (serial.SerialException, UnicodeDecodeError) as exc:
                self._log.error("Failed to read interface %s: %s", name, exc)
        return data

    def interface_config(self, name: str) -> dict:
        """Return the config dict for an interface.

        Args:
            name: The interface name.

        Returns:
            The interface config, or an empty dict if unknown.
        """
        return self._interfaces().get(name, {})

    def close(self) -> None:
        """Close all open serial interfaces.

        Returns:
            None.
        """
        for name, handle in self._ports.items():
            try:
                handle.close()
            except AttributeError:
                self._log.debug("No open serial interface to close for %s", name)
