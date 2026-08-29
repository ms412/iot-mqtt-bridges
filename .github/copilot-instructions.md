# Copilot Instructions

## Environment and verification

- Target Python is 3.12+; do not use syntax introduced by a later release.
- Install the runtime dependencies with `pip install -r requirements.txt`.
- `AGENTS.md` defines the repository lint command as `ruff check .` and formatting command as
  `ruff format .`. Ruff is not currently pinned in `requirements.txt`.
- `AGENTS.md` defines the full test command as
  `pytest tests/ -v --cov=common --cov=modbus2mqtt ...`. There are currently no test files in
  the repository. When tests are added, run one test with
  `pytest tests/<bridge>/test_<module>.py::test_<name>`.

## Architecture

The active application is a configuration-driven Modbus-to-MQTT polling service:

1. [`modbus2mqtt/main.py`](../modbus2mqtt/main.py) is the executable entry point used by
   [`systemd/modbus2mqtt.service`](../systemd/modbus2mqtt.service). It creates `Modbus2mqtt`,
   loads YAML, configures logging, starts MQTT, creates one Modbus client per configured slave,
   then polls indefinitely.
2. The main YAML has `LOGGING`, `BROKER`, and `MODBUS` sections. A device entry under `MODBUS`
   identifies a slave and references a register-definition YAML file using `FILE`; `QUERY`
   optionally limits that device to named registers. Device definitions may put `REGISTERS` at
   the root or beneath a single slave-ID key.
3. [`modbus2mqtt/modbus.py`](../modbus2mqtt/modbus.py) owns protocol access. It selects the
   connection type from `MODBUS.INTERFACE`, reads function codes `0x03` and `0x04`, and decodes
   the configured Modbus data type.
4. `Modbus2mqtt.getModbusData()` applies each register's `Scale Factor` and optional
   `Value Range min`/`Value Range max`, producing `{slave: {register: {VALUE, UNIT}}}`.
   `publishData()` publishes each slave payload as JSON to `<BROKER.PUBLISH>/<slave>`.
5. [`common/mqtt/mqtt_client.py`](../common/mqtt/mqtt_client.py) is the sole wrapper around
   Paho MQTT. It owns the asynchronous Paho network loop, retained last-will status, callback
   subscriptions, JSON conversion, and reconnect handling. Do not add direct Paho client usage
   outside this module.

## Repository-specific conventions

- Keep operational values in YAML; the service resolves both the main configuration and its
  referenced device definitions relative to the project root computed by `modbus2mqtt/main.py`.
  Update `FILE` references whenever config files move.
- Extend device support by adding or updating register-definition YAML, not by embedding
  register addresses, sizes, data types, or scaling in Python. Preserve the keys consumed by
  the polling flow: `Name`, `Function Codes`, `Start`, `Size`, `Data Type`, `Unit`, and
  `Scale Factor`.
- `QUERY` is an allowlist of register names. Omit it to poll every register in that device
  definition. Legacy Excel-based register definitions are explicitly unsupported.
- Preserve the MQTT topic contract: the configured `PUBLISH` topic is the base, and the slave
  ID is appended by the application. `LWT_TOPIC` is used for retained online/offline state.
- Keep Modbus I/O in [`modbus2mqtt/modbus.py`](../modbus2mqtt/modbus.py) and MQTT lifecycle
  behavior in [`common/mqtt/mqtt_client.py`](../common/mqtt/mqtt_client.py); coordinate changes
  across the caller and these helpers when changing their method signatures or payload shapes.
- Use the project logger configuration in [`common/logging/app_logger.py`](../common/logging/app_logger.py)
  for application logging. Avoid bypassing it with an independently configured logger.
- The deployment unit runs `modbus2mqtt/main.py` from `/opt/modbus2mqtt`; preserve that path contract or
  update [`systemd/modbus2mqtt.service`](../systemd/modbus2mqtt.service) with any entry-point
  relocation.
