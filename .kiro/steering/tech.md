# Tech Stack

## Language & Runtime

- Python 3.12+ (do not use syntax from later releases).
- Modern type hints are used in `src/main.py` (`str | None`, `list[dict]`, etc.).

## Key Dependencies (see `requirements.txt`)

- `pymodbus==3.5.4` — Modbus TCP/RTU/UDP/TLS client and payload decoding.
- `paho-mqtt==2.1.0` — MQTT client (wrapped by `common/mqtt/mqtt_client.py`).
- `pyserial==3.5` — serial transport for Modbus RTU.
- `pyyaml>6.0.0` — config parsing.

Note: `AGENTS.md` lists `pytest`, `pytest-mock`, and `ruff` and a `paho-mqtt>=2.0`
minimum, but those tools are **not** currently pinned in `requirements.txt`, and there
is no `pyproject.toml` or `tests/` directory in the repo.

## Common Commands

Run from the project root so package imports resolve.

```powershell
# Install dependencies
pip install -r requirements.txt

# Run the bridge with a specific config (relative to project root)
python src/main.py modbus2mqtt/config/modbus2mqtt_photovoltaic.yaml
```

The config path passed on the CLI is resolved relative to the project root (the parent
of `src/`). `FILE:` references inside a config are also resolved from the project root.

## Deployment

`systemd/modbus2mqtt.service` runs `/opt/modbus2mqtt/.venv/bin/python
/opt/modbus2mqtt/src/main.py` with `WorkingDirectory=/opt/modbus2mqtt` and
`Restart=on-failure`. Preserve that path contract or update the unit file if the entry
point moves.

## Conventions (actual code)

The existing code predates most of the `AGENTS.md` style rules, so expect divergence:

- `common/mqtt/mqtt_client.py` and `modbus2mqtt/modbus.py` call
  `logging.getLogger(...)` directly rather than routing through `common/logging/app_logger.py`.
- There are a few `print()` calls (e.g. config errors in `src/main.py`, a debug print in
  `mqttclient.connect`). `AGENTS.md` forbids `print()`; new code should prefer the logger.
- The MQTT wrapper class is named `mqttclient` (lowercase) and uses camelCase methods
  (`stateUpdate`, `setConnectionLostCallback`). Match the surrounding style when editing
  existing files.
- The poll loop in `src/main.py` uses `time.sleep()` with an unconditional `while True`.

## When Making Changes

- Keep Modbus I/O in `modbus2mqtt/modbus.py` and MQTT lifecycle in
  `common/mqtt/mqtt_client.py`. Do not add Paho usage elsewhere.
- Add device support via register-definition YAML, not hardcoded Python.
- Keep operational values (hosts, ports, topics, baud rates) in YAML.
- Coordinate signature/payload changes across `src/main.py` and the two helper modules.
- There is currently no automated test or lint setup wired up; verify changes by running
  the service against a config where feasible, and state what could not be verified.
