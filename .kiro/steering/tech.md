# Tech Stack

## Language & Runtime

- Python 3.12+ (do not use syntax from later releases).
- Modern type hints are used throughout (`str | None`, `list[tuple[...]]`, etc.).

## Key Dependencies (see `requirements.txt`)

- `pymodbus==3.5.4` — Modbus TCP/RTU/UDP/TLS client and payload decoding.
- `paho-mqtt==2.1.0` — MQTT client (wrapped by `common/mqtt/mqtt_client.py`).
- `pyserial==3.5` — serial transport for Modbus RTU, M-Bus, SML, and S0.
- `pyMeterBus==0.8.4` — M-Bus protocol (imported as `meterbus`).
- `smllib==1.2` — SML smart-meter parsing.
- `websocket-client==1.8.0` — Sungrow inverter WebSocket (imported as `websocket`).
- `pyyaml>6.0.0` — config parsing.
- `pytest>=8.0` / `pytest-mock>=3.12` — test dependencies.

Note: the installed pymodbus must match the pinned `3.5.4`; later 3.x releases moved
APIs that `modbus2mqtt/modbus.py` relies on. `pyproject.toml` is not yet created.

## Common Commands

Run from the project root so package imports resolve.

```powershell
# Install dependencies
pip install -r requirements.txt

# Run a bridge as a module with a specific config (relative to project root)
python -m modbus2mqtt.main modbus2mqtt/config/modbus2mqtt_photovoltaic.yaml

# Run the test suite
pytest test/
```

The config path passed on the CLI is resolved relative to the project root. `FILE:`
references inside a config are resolved relative to the bridge directory.

## Deployment

Each bridge has a `systemd/<bridge>.service` unit running
`/opt/iot-mqtt-bridges/.venv/bin/python -m <bridge>.main <config>` with
`WorkingDirectory=/opt/iot-mqtt-bridges` and `Restart=on-failure`. An optional Docker
setup (`docker/<bridge>.Dockerfile` + `docker-compose.yml`) is also provided.

## Conventions (actual code)

The codebase follows PEP 8: `PascalCase` classes (`MqttClient`, `AppLogger`,
`BaseConfig`, `Modbus2Mqtt`), `snake_case` methods, type hints, and Google-style
docstrings.

- `common/mqtt/mqtt_client.py` and `modbus2mqtt/modbus.py` still call
  `logging.getLogger(...)` directly rather than routing through
  `common/logging/app_logger.py`; that is acceptable for those library modules.
- New code must use the logger, not `print()`.
- Bridges expose the lifecycle methods `load_config`, `start_logging`, `start_mqtt`,
  `connect_source`, `read_data`, `map_to_topics`, `publish_data`, `run`/`stop`.

## When Making Changes

- Keep Modbus I/O in `modbus2mqtt/modbus.py` / the bridge reader, and MQTT lifecycle in
  `common/mqtt/mqtt_client.py`. Do not add Paho usage elsewhere.
- Add device support via register-definition YAML, not hardcoded Python.
- Keep operational values (hosts, ports, topics, baud rates) in YAML.
- Coordinate signature/payload changes across a bridge's `main.py`, reader, and mapper.
- Run `pytest test/` before committing; the pre-commit hook enforces this.
