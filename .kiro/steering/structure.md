# Project Structure

## Layout (as it exists today)

```
iot-mqtt-bridges/
├── src/
│   ├── main.py            # REAL entry point (systemd runs this). Defines Modbus2mqtt.
│   └── __init__.py
├── common/                # Shared library
│   ├── mqtt/
│   │   └── mqtt_client.py # `mqttclient` — Paho MQTT wrapper (connect/publish/subscribe/LWT)
│   └── logging/
│       └── logger.py      # `logger` — dictConfig-based logger factory
├── modbus2mqtt/
│   ├── modbus.py          # `Modbus` — pymodbus wrapper (read + decode registers)
│   ├── main.py            # EMPTY (do not assume this is the entry point)
│   └── config/
│       ├── modbus2mqtt_photovoltaic.yaml   # main config example
│       ├── modbus2mqtt_waterlevel.yaml     # main config example
│       ├── devices/       # per-device register definitions (SDM120, QDY30A, Solarcheck)
│       └── data/          # reference material (PDF, Register.xlsx)
├── systemd/modbus2mqtt.service
├── requirements.txt
├── AGENTS.md              # aspirational architecture / conventions
└── .github/copilot-instructions.md
```

## Important Reality Checks

- **Entry point is `src/main.py`**, not `modbus2mqtt/main.py` (which is empty). The
  systemd unit and CLI (`python src/main.py <config.yaml>`) both use `src/main.py`.
- The `Modbus2mqtt` application class lives in `src/main.py`, imports `Modbus` from
  `modbus2mqtt.modbus` and `mqttclient`/`logger` from `common`.
- Package `__init__` files are currently misnamed as `__init.py__` /  `__init.py___`
  in `common/` and `modbus2mqtt/`. Only `src/__init__.py` is correctly named. Imports
  work because scripts run from the project root.

## Module Responsibilities

- `src/main.py` — orchestration: load YAML, resolve device-definition files, start
  logger + MQTT + Modbus clients, poll loop, scale/clamp values, publish JSON.
- `modbus2mqtt/modbus.py` — all Modbus I/O and decoding. Function codes `0x03`
  (holding) and `0x04` (input) are implemented; data-type decoding via
  `BinaryPayloadDecoder`.
- `common/mqtt/mqtt_client.py` — the only place Paho MQTT is used. Owns loop,
  reconnect, retained LWT, JSON encode/decode, topic callbacks.
- `common/logging/app_logger.py` — `AppLogger` setup for CONSOLE / SYSLOG / FILE modes.

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
- Status: `BROKER.LWT_TOPIC` carries retained `ONLINE` / `OFFLINE`.

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
