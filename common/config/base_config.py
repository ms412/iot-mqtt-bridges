#!/usr/bin/env python3
"""YAML configuration loading shared by all bridges."""

import logging
from pathlib import Path

import yaml


class BaseConfig:
    """Load a bridge YAML config and resolve device-definition references.

    Paths are resolved relative to the project root so a bridge can be launched
    from any working directory. Device ``FILE`` references in the ``MODBUS``
    section are expanded into ``REGISTERS`` lists, optionally narrowed by a
    ``QUERY`` allowlist.
    """

    def __init__(self, configfile: str) -> None:
        """Initialize the loader.

        Args:
            configfile: Path to the config file, relative to the project root.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"modbus2mqtt.{_lib_name}.{self.__class__.__name__}")

        self._configfile = configfile
        self._data: dict = {}

    @property
    def project_root(self) -> Path:
        """Return the project root directory.

        Returns:
            The parent directory of the ``common`` package.
        """
        return Path(__file__).resolve().parents[2]

    @property
    def data(self) -> dict:
        """Return the parsed configuration.

        Returns:
            The configuration dict, empty until :meth:`read` has been called.
        """
        return self._data

    @property
    def _device_base(self) -> Path:
        """Return the base directory for resolving device ``FILE`` references.

        Bridge configs live in ``<bridge>/config/`` and reference device files
        as ``config/devices/<name>.yaml`` relative to the bridge directory, so
        the base is the parent of the config file's directory.

        Returns:
            The directory that device ``FILE`` references resolve against.
        """
        return (self.project_root / self._configfile).resolve().parent.parent

    def _read_yaml(self, path: Path) -> dict:
        """Read and parse a YAML file.

        Args:
            path: Absolute path to the YAML file.

        Returns:
            The parsed YAML content, or an empty dict if the file is empty.
        """
        with path.open(mode="r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _load_device_definition(self, file_reference: str) -> dict:
        """Load a device definition file and return its register container.

        The register list may live at the file root under ``REGISTERS`` or be
        nested beneath a single slave-id key.

        Args:
            file_reference: Relative path to the device definition YAML file.

        Returns:
            The device definition dict containing a ``REGISTERS`` list.

        Raises:
            ValueError: If the reference is empty or no ``REGISTERS`` list exists.
        """
        if not file_reference:
            raise ValueError("Device definition file reference is empty.")

        device: dict = self._read_yaml(self._device_base / file_reference)
        if not isinstance(device, dict):
            raise ValueError(f"Invalid device definition file: {file_reference}")

        if "REGISTERS" in device:
            return device

        if len(device) == 1:
            nested = next(iter(device.values()))
            if isinstance(nested, dict) and "REGISTERS" in nested:
                return nested

        raise ValueError(
            f"The device definition file does not contain a REGISTERS list: {file_reference}"
        )

    def _filter_registers(self, registers: list[dict], query: list | None) -> list[dict]:
        """Keep only the registers named in the ``QUERY`` allowlist.

        Args:
            registers: Full register list loaded from a device file.
            query: Requested register names, or None to keep everything.

        Returns:
            The filtered register definitions.
        """
        if query is None:
            return registers

        wanted: set = set()
        for entry in query:
            if isinstance(entry, dict):
                wanted.add(entry.get("Name", entry.get("name")))
            else:
                wanted.add(str(entry))

        return [reg for reg in registers if reg.get("Name") in wanted]

    def _resolve_devices(self) -> None:
        """Resolve ``FILE`` references in the MODBUS section into ``REGISTERS``.

        Returns:
            None. The MODBUS section is updated in place.
        """
        modbus = self._data.get("MODBUS")
        if not isinstance(modbus, dict):
            return

        for device_id, device in list(modbus.items()):
            if not isinstance(device, dict) or "FILE" not in device:
                continue

            loaded = self._load_device_definition(device["FILE"])
            registers = loaded.get("REGISTERS", [])
            registers = self._filter_registers(registers, device.get("QUERY"))

            resolved = {key: value for key, value in device.items() if key != "FILE"}
            resolved["REGISTERS"] = registers
            modbus[device_id] = resolved

    def read(self) -> dict:
        """Read the config file and resolve referenced device definitions.

        Returns:
            The parsed configuration with device ``FILE`` references resolved
            into ``REGISTERS`` lists.
        """
        self._data = self._read_yaml(self.project_root / self._configfile)
        self._resolve_devices()
        return self._data

    @classmethod
    def load(cls, configfile: str) -> "BaseConfig":
        """Create a ``BaseConfig`` and immediately read the file.

        Args:
            configfile: Path to the config file, relative to the project root.

        Returns:
            A populated ``BaseConfig`` instance.
        """
        instance = cls(configfile)
        instance.read()
        return instance
