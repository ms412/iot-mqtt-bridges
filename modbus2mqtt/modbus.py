#!/usr/bin/env python3
"""pymodbus wrapper for reading and decoding Modbus registers."""

import logging

from pymodbus.client import (
    ModbusSerialClient,
    ModbusTcpClient,
    ModbusTlsClient,
    ModbusUdpClient,
)
from pymodbus.constants import Endian
from pymodbus.exceptions import ModbusException
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.transaction import ModbusRtuFramer, ModbusSocketFramer

__APP__ = "modbus2mqtt"


class Modbus:
    """Read and decode registers from a single Modbus slave.

    Supports TCP, UDP, serial (RTU), and TLS transports, function codes 0x03
    (holding registers) and 0x04 (input registers), and the common integer,
    float, and string data types.
    """

    def __init__(self, slave: int, endian: str = "BIG") -> None:
        """Initialize the client for a slave id.

        Args:
            slave: The Modbus slave/unit id.
            endian: Byte/word order, ``"BIG"`` (default) or ``"LITTLE"``.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{__APP__}.{_lib_name}.{self.__class__.__name__}")

        self._client = None
        self._slave = int(slave)
        self._endian = Endian.BIG if endian == "BIG" else Endian.LITTLE

    def connect(self, comm: str, **kwargs) -> None:
        """Create and open a Modbus client for the given transport.

        Args:
            comm: Transport type: ``"tcp"``, ``"udp"``, ``"serial"``, or ``"tls"``.
            **kwargs: Transport parameters (``host``, ``port``, ``baudrate``).

        Returns:
            None.
        """
        if comm == "tcp":
            self._client = ModbusTcpClient(
                kwargs.get("host"),
                port=kwargs.get("port", 502),
                framer=ModbusSocketFramer,
            )
        elif comm == "udp":
            self._client = ModbusUdpClient(
                kwargs.get("host"),
                port=kwargs.get("port", 502),
                framer=ModbusSocketFramer,
            )
        elif comm == "serial":
            self._client = ModbusSerialClient(
                kwargs.get("port", "/dev/ttyUSB0"),
                framer=ModbusRtuFramer,
                timeout=2,
                baudrate=kwargs.get("baudrate", 9600),
                bytesize=8,
                parity="N",
                stopbits=1,
            )
        elif comm == "tls":
            self._client = ModbusTlsClient(
                kwargs.get("host"),
                port=kwargs.get("port", 502),
                framer=ModbusSocketFramer,
                certfile="../examples/certificates/pymodbus.crt",
                keyfile="../examples/certificates/pymodbus.key",
                server_hostname="localhost",
            )
        else:
            self._log.error("Unknown client transport selected: %s", comm)
            return

        self._client.connect()
        assert self._client.connected

    def get_data(self, function_code: str, **kwargs) -> object:
        """Read a register value using the given function code.

        Args:
            function_code: Modbus function code, ``"0x03"`` (holding) or
                ``"0x04"`` (input).
            **kwargs: ``address`` (int), ``size`` (int), and ``datatype`` (str).

        Returns:
            The decoded register value, or None on error/unknown function code.
        """
        data = None
        if function_code == "0x03":
            self._log.debug("Slave %d function code 0x03", self._slave)
            data = self._read_holding_registers(
                int(kwargs.get("address")),
                int(kwargs.get("size")),
                str(kwargs.get("datatype")),
            )
        elif function_code == "0x04":
            self._log.debug("Slave %d function code 0x04", self._slave)
            data = self._read_input_registers(
                int(kwargs.get("address")),
                int(kwargs.get("size")),
                str(kwargs.get("datatype")),
            )
        else:
            self._log.error("Function code unknown: %s", function_code)

        return data

    def _read_holding_registers(self, address: int, size: int, data_type: str) -> object:
        """Read and decode holding registers (function code 0x03).

        Args:
            address: Start register address.
            size: Number of registers to read.
            data_type: Decoding data type (e.g. ``"float32"``).

        Returns:
            The decoded value, or None on error.
        """
        try:
            resp = self._client.read_holding_registers(address, size, self._slave)
        except ModbusException as exc:
            self._log.error("ModbusException on holding read: %s", exc)
            self._client.close()
            return None
        if resp.isError():  # pragma: no cover
            self._log.error("Modbus library error: %s", resp)
            self._client.close()
            return None

        msg = BinaryPayloadDecoder.fromRegisters(
            resp.registers, byteorder=self._endian, wordorder=self._endian
        )
        return self._decode_message(msg, data_type)

    def _read_input_registers(self, address: int, size: int, data_type: str) -> object:
        """Read and decode input registers (function code 0x04).

        Args:
            address: Start register address.
            size: Number of registers to read.
            data_type: Decoding data type (e.g. ``"float32"``).

        Returns:
            The decoded value, or None on error.
        """
        self._log.debug("Read input register %d, %d, %s", address, size, data_type)
        try:
            resp = self._client.read_input_registers(address, size, self._slave)
        except ModbusException as exc:
            self._log.error("ModbusException on input read: %s", exc)
            self._client.close()
            return None
        if resp.isError():  # pragma: no cover
            self._log.error("Modbus library error: %s", resp)
            self._client.close()
            return None

        msg = BinaryPayloadDecoder.fromRegisters(
            resp.registers, byteorder=self._endian, wordorder=self._endian
        )
        return self._decode_message(msg, data_type)

    def _decode_message(self, data: BinaryPayloadDecoder, data_type: str = "uint32") -> object:
        """Decode a register payload into a Python value.

        Args:
            data: The payload decoder positioned at the start of the value.
            data_type: The declared data type of the value.

        Returns:
            The decoded value, or False when the data type is unknown.
        """
        if data_type == "int32":
            return data.decode_32bit_int()
        if data_type == "uint32":
            return data.decode_32bit_uint()
        if data_type == "uint64":
            return data.decode_64bit_uint()
        if data_type == "STR16":
            return data.decode_string(6)
        if data_type == "STR32":
            return data.decode_string(32)
        if data_type == "STR":
            return data.decode_string(8)
        if data_type == "int16":
            return data.decode_16bit_int()
        if data_type == "uint16":
            return data.decode_16bit_uint()
        if data_type == "uint8":
            return data.decode_8bit_uint()
        if data_type == "floa16":
            return data.decode_16bit_float()
        if data_type == "float32":
            return data.decode_32bit_float()
        if data_type == "float64":
            return data.decode_64bit_float()

        self._log.error("Unknown data type: %s", data_type)
        return False
