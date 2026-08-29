#!/usr/bin/env python3
"""SML serial I/O and frame extraction for the sml2mqtt bridge."""

import logging
import time

import serial

from sml2mqtt.sml_obis import SML_END, SML_START, get_crc

__APP__ = "sml2mqtt"


class SmlReader:
    """Read complete, CRC-validated SML frames from a serial interface."""

    def __init__(self, sml_config: dict) -> None:
        """Initialize the reader.

        Args:
            sml_config: The SML section of the bridge config.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{__APP__}.{_lib_name}.{self.__class__.__name__}")

        self._config = sml_config or {}
        self._serial = None

    def connect(self) -> None:
        """Open the SML serial interface (8N1, 1s timeout).

        Returns:
            None.
        """
        device = str(self._config.get("SERIAL", "/dev/ttyUSB0"))
        baudrate = int(self._config.get("BAUDRATE", 9600))

        self._serial = serial.Serial(
            port=device,
            baudrate=baudrate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1.0,
        )
        self._log.info("SML serial opened on %s @ %d baud", device, baudrate)

    def _read_buffer(self) -> bytes:
        """Read whatever is currently available from the serial port.

        Returns:
            The bytes read from the port.
        """
        buffer = self._serial.read()  # block until at least one byte arrives
        time.sleep(1)  # let the input buffer fill
        buffer += self._serial.read(self._serial.in_waiting)
        return buffer

    def read_frame(self) -> bytes | None:
        """Read one complete, CRC-valid SML frame.

        Returns:
            The framed bytes, or None when no valid frame is available.
        """
        try:
            buffer = self._read_buffer()
        except serial.SerialException as exc:
            self._log.error("Serial read failed: %s", exc)
            return None

        if SML_START not in buffer or SML_END not in buffer:
            self._log.debug("No complete SML frame in buffer")
            return None

        p0 = buffer.index(SML_START)
        p1 = buffer.index(SML_END)

        crc_msg = buffer[-2] << 8 | buffer[-1]
        crc_calc = get_crc(buffer[:-2])
        if crc_msg != crc_calc:
            self._log.error("CRC failure on SML frame")
            return None

        self._log.debug("Good SML frame")
        return buffer[p0:p0 + p1 + len(SML_END) + 3]

    def close(self) -> None:
        """Close the serial interface if it is open.

        Returns:
            None.
        """
        try:
            self._serial.close()
        except AttributeError:
            self._log.debug("No open serial interface to close")
