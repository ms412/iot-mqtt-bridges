# Project Structure

## Layout (as it exists today)

```
iot-mqtt-bridges/
├── common/                # Shared library
│   ├── mqtt/
│   │   └── mqtt_client.py # `MqttClient` — Paho MQTT wrapper (connect/publish/subscribe/LWT)
│   ├── logging/
│   │   └── app_logger.py  # `AppLogger` — dictConfig-based logger factory
│   └── config/
│       └── base_config.py # `BaseConfig` — YAML loader + device-file resolution
├── modbus2mqtt/
│   ├── main.py            # entry point: Modbus2Mqtt coordinator + main()
│   ├── modbus.py          # `Modbus` — pymodbus wrapper (read + decode registers)
│   ├── modbus_reader.py   # `ModbusReader` — one Modbus client per slave
│   ├── modbus_mapper.py   # pure functions: scale/clamp + topic/payload
│   └── config/
│       ├── modbus2mqtt_photovoltaic.yaml   # main config example
│       ├── modbus2mqtt_waterlevel.yaml     # main config example
│       ├── devices/       # per-device register definitions (SDM120, QDY30A, Solarcheck)
│       └── data/          # reference material (PDF, Register.xlsx)
├── mbus2mqtt/ · sml2mqtt/ · so2mqtt/ · sungrow2mqtt/   # the other four bridges
├── systemd/               # one unit per bridge
├── docker/                # optional per-bridge Dockerfiles
├── test/                  # pytest suites mirroring the source layout
├── requirements.txt
├── AGENTS.md              # aspirational architecture / conventions
└── .github/copilot-instructions.md
```

## Important Reality Checks

- **Entry point is `modbus2mqtt/main.py`**, run as a module: `python -m
  modbus2mqtt.main <config.yaml>`. The legacy `src/main.py` monolith has been removed;
  its logic now lives in `modbus2mqtt/main.py` + `modbus_reader.py` + `modbus_mapper.py`.
- The `Modbus2Mqtt` coordinator class lives in `modbus2mqtt/main.py` and imports
  `Modbus` from `modbus2mqtt.modbus`, plus `MqttClient` / `AppLogger` / `BaseConfig`
  from `common`.
- Scripts are run from the project root so `common.*` and the bridge packages resolve.

## Module Responsibilities

- `modbus2mqtt/main.py` — orchestration: load YAML, start logging + MQTT + Modbus,
  poll loop, publish JSON.
- `modbus2mqtt/modbus_reader.py` — builds one `Modbus` client per slave and reads
  registers.
- `modbus2mqtt/modbus_mapper.py` — pure functions: scale, clamp, and build topic/payload.
- `modbus2mqtt/modbus.py` — all Modbus I/O and decoding. Function codes `0x03`
  (holding) and `0x04` (input) are implemented; data-type decoding via
  `BinaryPayloadDecoder`.
- `common/mqtt/mqtt_client.py` — the only place Paho MQTT is used. Owns loop,
  reconnect, retained LWT, JSON encode/decode, topic callbacks.
- `common/logging/app_logger.py` — `AppLogger` setup for CONSOLE / SYSLOG / FILE modes.
- `common/config/base_config.py` — `BaseConfig` YAML loader + device-file resolution.

## Config Model

Main config YAML uses UPPERCASE top-level keys: `LOGGING`, `BROKER`, `MODBUS`.
(Note: this differs from the lowercase schema in `AGENTS.md`.)

- `MODBUS` holds transport settings (`INTERFACE`, `HOST`, `BAUDRATE`,
  `UPDATE_INTERVAL`, `STARTUP_DELAY`) plus one entry per slave ID.
- Each slave entry references a device file via `FILE:` and may narrow readings with a
  `QUERY:` allowlist of register names.
- Device files contain a `REGISTERS` list (at root or nested under a single slave-ID
  key). Register keys consumed by the code: `Name`, `Function Codes`, `Start`, `Size`,
  `Data Type`, `Unit`, `Scale Factor`, plus optional `Value Range min` / `Value Range max`.

## MQTT Topic Contract

- modbus2mqtt payload topic: `<BROKER.PUBLISH>/<slaveId>` with a JSON body of
  `{registerName: {VALUE, UNIT}}`.
- mbus2mqtt payload topic: `<BROKER.PUBLISH>/<slaveId>` with a JSON body of
  `{METRIC: value}`.
- sml2mqtt payload topic: `<BROKER.PUBLISH>` (single topic) with a JSON body keyed by
  OBIS short code: `{obis_short: {data_value, data_unit, data_type}}`.
- so2mqtt payload topic: `<BROKER.PUBLISH>/<interface>/<channel>` (retained) with a JSON
  body of `{S0, S0_raw}`.
- sungrow2mqtt payload topic: `<BROKER.PUBLISH>/<dev_id>` with a flattened JSON body of
  `{measurement: value | {value, unit}, ...}`.
- Status: `BROKER.LWT_TOPIC` carries retained `ONLINE` / `OFFLINE`.
- All bridges add a top-level `timestamp` (Unix epoch seconds) to every payload.

## mbus2mqtt Package

Adapted from github.com/ms412/mbus2mqtt, following the same shape as modbus2mqtt and
reusing `common/` (`mqttclient`, `logger`, `BaseConfig`).

```
mbus2mqtt/
├── __init__.py
├── main.py          # Mbus2Mqtt coordinator class + thin main()
├── mbus_reader.py   # MbusReader — pyMeterBus serial I/O (ping/ACK/request/long telegram)
├── mbus_mapper.py   # pure functions: applyOffset, mapSlave, buildPayload, mapToTopics
└── config/
    └── mbus2mqtt.yaml
```

- Config uses UPPERCASE keys `LOGGING`, `BROKER`, `MBUS`. The `MBUS` section holds
  transport settings (`DEVICE`, `BAUDRATE`, `UPDATE_INTERVAL`, `STARTUP_DELAY`) plus one
  entry per M-Bus address, each with an optional `METRIC` label (default `WATER`) and
  additive `OFFSET`.
- `Mbus2Mqtt` mirrors `Modbus2Mqtt`: `loadConfig`, `startLogging`, `startMqtt`,
  `connectSource`, `readData`, `mapToTopics`, `publishData`, `run` / `stop`.
- The reader reads each slave's primary record value (`body.records[0].value`) via
  `meterbus` and adds the configured `OFFSET`.

## sml2mqtt Package

Adapted from github.com/ms412/SML2mqtt, following the same shape as the other bridges
and reusing `common/` (`mqttclient`, `logger`, `BaseConfig`).

```
sml2mqtt/
├── __init__.py
├── main.py          # Sml2Mqtt coordinator class + thin main()
├── sml_reader.py    # SmlReader — serial I/O, frame extraction, CRC-16/X25 validation
├── sml_mapper.py    # parseFrame (via smllib), buildPayload, mapToTopics
├── sml_obis.py      # SML_START/END markers, UNITS, OBIS_NAMES, CRC table + get_crc
└── config/
    └── sml2mqtt.yaml
```

- Config uses UPPERCASE keys `LOGGING`, `BROKER`, `SML`. The `SML` section holds
  `SERIAL`, `BAUDRATE`, `UPDATE_INTERVAL`, `STARTUP_DELAY`.
- `Sml2Mqtt` mirrors the other bridges: `loadConfig`, `startLogging`, `startMqtt`,
  `connectSource`, `readData`, `mapToTopics`, `publishData`, `run` / `stop`.
- The reader extracts a complete `SML_START`..`SML_END` frame from the serial buffer and
  validates its CRC before handing raw bytes to `sml_mapper.parseFrame`, which uses
  `smllib.SmlStreamReader` to decode OBIS values.
- NOTE: the upstream repo used `configobj` (INI `.config`); here it is converted to the
  project's YAML `BaseConfig`.

## so2mqtt Package

Adapted from github.com/ms412/S02mqtt, following the same shape as the other bridges and
reusing `common/` (`mqttclient`, `logger`, `BaseConfig`). Depends only on `pyserial`.

```
so2mqtt/
├── __init__.py
├── main.py          # So2Mqtt coordinator class + thin main()
├── so_reader.py     # So0Reader — serial query ($?), one port per interface
├── so_mapper.py     # extractChannel / processInterface / mapToTopics
└── config/
    └── so2mqtt.yaml
```

- Config uses UPPERCASE keys `LOGGING`, `BROKER`, `S0`. The `S0` section holds
  `UPDATE_INTERVAL` / `STARTUP_DELAY` plus one entry per serial interface (e.g.
  `SERIAL01`) with `PORT` / `BAUDRATE` and one nested entry per channel, each with
  `BYTE` (field index), `FACTOR` (divisor), and `OFFSET` (additive).
- `So2Mqtt` mirrors the other bridges: `loadConfig`, `startLogging`, `startMqtt`,
  `connectSource`, `readData`, `mapToTopics`, `publishData`, `run` / `stop`. Readings are
  published retained.
- The reader queries each interface once per cycle (writes `$?`, reads a `;`-separated
  line) and the mapper derives each channel's value from the chosen field.
- NOTE: the upstream repo used `configobj` (nested INI `.config`); here it is converted
  to the project's YAML `BaseConfig`.

## sungrow2mqtt Package

Adapted from github.com/ms412/sungrow2mqtt, following the same shape as the other
bridges and reusing `common/` (`MqttClient`, `AppLogger`, `BaseConfig`). Depends on
`websocket-client`.

```
sungrow2mqtt/
├── __init__.py
├── main.py             # Sungrow2Mqtt coordinator class + thin main()
├── sungrow_reader.py   # SungrowReader — WiNet-S WebSocket (connect/auth/devicelist/real/direct/ping)
├── sungrow_mapper.py   # flatten_measurements / process_device / build_payload / map_to_topics
└── config/
    └── sungrow2mqtt.yaml
```

- Config uses UPPERCASE keys `LOGGING`, `BROKER`, `SUNGROW`. The `SUNGROW` section holds
  `HOST` / `PORT` / `TLS` / `USERNAME` / `PASSWORD` / `LANG` / `TIMEOUT` plus
  `UPDATE_INTERVAL` / `STARTUP_DELAY`. `PASSWORD` uses `${SUNGROW_PASSWORD}`, resolved
  from the environment in `main.py` (`BaseConfig` does not expand env vars).
- `Sungrow2Mqtt` mirrors the other bridges: `load_config`, `start_logging`,
  `start_mqtt`, `connect_source`, `read_data`, `map_to_topics`, `publish_data`,
  `run` / `stop`. The run loop uses `SungrowReader.ping()` for keepalive and reconnects
  on failure.
- The reader connects over `wss://<host>:<port>/ws/home/overview` with TLS verification
  disabled (self-signed WiNet-S certificate; LAN-only), authenticates (connect + login),
  then lists devices and attaches each device's `real` and `direct` measurement lists.
- NOTE: the upstream repo used `.env` + pydantic-settings; here it is converted to the
  project's YAML `BaseConfig` with `${VAR}` env references for secrets.

## Docker (optional)

Optional container deployment; nothing in the Python code depends on it. Per-bridge
Dockerfiles live in `docker/<bridge>.Dockerfile` (base `python:3.12-slim`) and
`docker-compose.yml` defines all five services with `restart: unless-stopped`. Config is
bind-mounted read-only, secrets come from a gitignored `.env` (see `.env.example`), and
serial bridges map a host `/dev/ttyUSB*` device.
