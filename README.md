# iot-mqtt-bridges

A Python monorepo of protocol-to-MQTT bridge services. Each bridge reads data
from an industrial/IoT device and publishes it to an MQTT broker for use by home
and building automation systems.

## Bridges

| Bridge        | Source protocol                         | Reads via     |
|---------------|-----------------------------------------|---------------|
| `modbus2mqtt` | Modbus TCP/RTU (holding/input registers) | `pymodbus`    |
| `mbus2mqtt`   | M-Bus (Meter-Bus) meters over serial     | `pyMeterBus`  |
| `sml2mqtt`    | SML (Smart Message Language) smart meters | `smllib`      |
| `so2mqtt`     | S0 pulse counters via a serial S0-USB adapter | `pyserial` |

All four are configuration-driven polling services that share the same
`common/` library (MQTT client, logger, and config loader).

## Repository Layout

```
iot-mqtt-bridges/
├── common/                # Shared library
│   ├── config/base_config.py   # BaseConfig: YAML loader + device-file resolution
│   ├── logging/app_logger.py   # AppLogger: logging setup (CONSOLE/FILE/SYSLOG)
│   └── mqtt/mqtt_client.py     # MqttClient: paho-mqtt wrapper (connect/publish/LWT)
├── modbus2mqtt/           # Modbus bridge (main.py, modbus_reader.py, modbus_mapper.py, modbus.py)
├── mbus2mqtt/             # M-Bus bridge (main.py, mbus_reader.py, mbus_mapper.py)
├── sml2mqtt/              # SML bridge (main.py, sml_reader.py, sml_mapper.py, sml_obis.py)
├── so2mqtt/               # S0 bridge (main.py, so_reader.py, so_mapper.py)
├── systemd/               # One systemd unit per bridge
├── test/                  # pytest suites mirroring the source layout
├── requirements.txt
├── AGENTS.md              # conventions for AI coding agents
└── LICENSE                # Beerware License (Revision 42)
```

## Architecture

Each bridge follows the same shape:

- **`main.py`** — a thin `main()` plus a coordinator class (e.g. `Modbus2Mqtt`)
  that owns the lifecycle: `load_config`, `start_logging`, `start_mqtt`,
  `connect_source`, `read_data`, `map_to_topics`, `publish_data`, `run`/`stop`.
- **`<protocol>_reader.py`** — protocol I/O only (serial/network), no MQTT.
- **`<protocol>_mapper.py`** — pure functions that transform raw readings into
  MQTT topic/payload pairs.

The `MqttClient` is created in the bridge and drives a retained online/offline
status via an MQTT Last Will topic.

## Configuration

Each bridge is driven by a YAML file under its `config/` directory with three
common uppercase sections:

```yaml
LOGGING:
  LOGMODE: CONSOLE        # CONSOLE | FILE | SYSLOG
  LOGFILE: modbus2mqtt.log
  LOGLEVEL: INFO          # DEBUG | INFO | WARNING | ERROR | CRITICAL

BROKER:
  BROKER: 192.168.4.31    # broker host/IP
  PORT: 1883
  PUBLISH: SMARTHOME/DE/IN/SENSOR01/PV01   # base publish topic
  LWT_TOPIC: SMARTHOME/DE/IN/SENSOR01/PV01/STATE
```

A protocol-specific section follows (`MODBUS`, `MBUS`, `SML`, or `S0`) holding
transport settings (`DEVICE`/`HOST`, `BAUDRATE`, `UPDATE_INTERVAL`,
`STARTUP_DELAY`) plus per-device or per-channel entries.

Credentials and secrets are supplied via environment variables, not committed to
config files.

### Published topics

- `modbus2mqtt`: `<PUBLISH>/<slaveId>` → `{register: {VALUE, UNIT}}`
- `mbus2mqtt`: `<PUBLISH>/<slaveId>` → `{METRIC: value}`
- `sml2mqtt`: `<PUBLISH>` (single topic) → `{obis_short: {data_value, data_unit, data_type}}`
- `so2mqtt`: `<PUBLISH>/<interface>/<channel>` → `{S0, S0_raw}` (retained)

## Installation

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Running a Bridge

Run from the repository root so `common.*` and the bridge packages resolve.
Each bridge accepts an optional config path (a sensible default is used
otherwise):

```bash
python -m modbus2mqtt.main modbus2mqtt/config/modbus2mqtt_photovoltaic.yaml
python -m mbus2mqtt.main   mbus2mqtt/config/mbus2mqtt.yaml
python -m sml2mqtt.main    sml2mqtt/config/sml2mqtt.yaml
python -m so2mqtt.main     so2mqtt/config/so2mqtt.yaml
```

Serial-based bridges (`mbus2mqtt`, `sml2mqtt`, `so2mqtt`) need access to the
serial device (on Linux, add the service user to the `dialout` group).

## Deployment (systemd)

Each bridge ships a unit in `systemd/`. Deploy the repo to
`/opt/iot-mqtt-bridges` with a `.venv` at its root, then:

```bash
sudo cp systemd/modbus2mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now modbus2mqtt.service
```

## Testing

Unit tests use `pytest` with `pytest-mock`; the MQTT client and all hardware I/O
are mocked (no real broker or device is contacted).

```bash
pytest test/
```

### Continuous integration and pre-commit

- **CI:** `.github/workflows/ci.yml` runs the test suite on every push and pull
  request across Python 3.12 and 3.13.
- **Pre-commit hook:** `.githooks/pre-commit` runs `pytest` and blocks the
  commit on failure. Enable it once per clone:

  ```bash
  git config core.hooksPath .githooks
  ```

## Conventions

Code follows PEP 8: PascalCase classes, snake_case functions and methods, type
hints on public methods, and Google-style docstrings. See `AGENTS.md` for the
full contributor conventions.

## License

Beerware License (Revision 42) — see [LICENSE](LICENSE). Author: Markus Schiesser
&lt;m.schiesser@gmail.com&gt;.
