# Product

## Overview

`iot-mqtt-bridges` is a Python monorepo intended to host several protocol-to-MQTT
bridge services that read data from industrial/IoT devices and publish it to an MQTT
broker for consumption by home/building automation systems.

## Current State

Five bridges are implemented today, all configuration-driven polling services:

**modbus2mqtt**
1. Reads holding/input registers from Modbus devices (RTU over serial, or TCP/UDP/TLS).
2. Applies scaling and value-range clamping to each register.
3. Publishes per-device readings as JSON to an MQTT broker.
4. Maintains a retained online/offline status via an MQTT Last Will topic.

**mbus2mqtt** (adapted from github.com/ms412/mbus2mqtt)
1. Reads M-Bus (Meter-Bus) meters over a serial interface using `pyMeterBus`.
2. Applies an optional additive `OFFSET` to each slave's primary record value.
3. Publishes per-slave readings as JSON (`{METRIC: value}`) to an MQTT broker.
4. Shares the same `common/` MQTT, logging, and config layer as modbus2mqtt.

**sml2mqtt** (adapted from github.com/ms412/SML2mqtt)
1. Reads SML (Smart Message Language) frames from a smart meter over serial.
2. Extracts a CRC-valid transport frame and parses OBIS values with `smllib`.
3. Publishes the parsed frame as JSON (keyed by OBIS short code) to an MQTT broker.
4. Shares the same `common/` MQTT, logging, and config layer as the other bridges.

**so2mqtt** (adapted from github.com/ms412/S02mqtt)
1. Reads S0 pulse-counter values from a serial S0-USB adapter (`$?` query).
2. Splits the `;`-separated response and, per channel, divides the chosen field by
   `FACTOR` and adds `OFFSET`.
3. Publishes per-channel readings as retained JSON (`{S0, S0_raw}`) to an MQTT broker.
4. Shares the same `common/` MQTT, logging, and config layer as the other bridges.

**sungrow2mqtt** (adapted from github.com/ms412/sungrow2mqtt)
1. Connects to a Sungrow inverter's WiNet-S dongle over a WebSocket and authenticates.
2. Lists devices and fetches each device's real-time and direct measurement lists.
3. Publishes per-device readings as JSON (flattened `{measurement: value}`) to MQTT.
4. Shares the same `common/` MQTT, logging, and config layer as the other bridges.

All four `AGENTS.md` target bridges plus `sungrow2mqtt` now exist, along with the
optional `docker/` setup. `BaseConfig` and `AppLogger` exist in `common/`; the
`BaseBridge` / `MqttConfig` abstractions described in `AGENTS.md` still do **not**.
Treat `AGENTS.md` as the target architecture and this steering as the description of
what is actually in the repo.

## Supported Devices

modbus2mqtt (via YAML register definitions):
- Phoenix Solarcheck SCK-C-MODBUS (photovoltaic)
- Eastron SDM120 single-phase energy meter
- QDY30A submersible water-level sensor

New Modbus device support is added by writing a register-definition YAML file, not by
editing Python.

mbus2mqtt: any M-Bus meter reachable on the serial bus; each address is configured
under the `MBUS` section with an optional `METRIC` label and `OFFSET`.

sml2mqtt: any SML smart meter on the serial interface; OBIS values are decoded via
`smllib` and labelled using the `UNITS` / `OBIS_NAMES` tables in `sml2mqtt/sml_obis.py`.

so2mqtt: S0 pulse-counter channels behind a serial S0-USB adapter; each interface and
its channels are configured under the `S0` section with `BYTE` / `FACTOR` / `OFFSET`.

sungrow2mqtt: a Sungrow inverter reachable over the LAN via its WiNet-S WebSocket;
connection settings live under the `SUNGROW` section (`HOST` / `PORT` / `TLS` /
`USERNAME` / `PASSWORD` / `LANG`). The password is supplied via `${SUNGROW_PASSWORD}`.

## Deployment

modbus2mqtt runs as a Linux `systemd` service (`systemd/modbus2mqtt.service`) from
`/opt/modbus2mqtt`, launching `src/main.py` inside a `.venv`. A comparable unit for
mbus2mqtt does not exist yet.
