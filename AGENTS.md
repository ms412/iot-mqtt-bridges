# AGENTS.md ” iot-mqtt-bridges

This file provides guidance for AI coding agents (e.g. OpenAI Codex, Claude, Copilot)
working on this repository. Read this before making any changes.

---
## Project Setup and Management

- Python version: 3.12+. Don't use newer syntax.
- Dependencies: Install via `pip install -r requirements.txt`
- Branch from `main` as `feature/<name>` and use Conventional Commits.
- Stage changes for review. Don't commit to `main` or push without
  being asked.

---

## Coding Conventions

- Type-hint public functions and methods, including their return types.
- Use `pathlib` for path management. Don't use `os.path`.
- Prefer f-strings over `str.format()` or `%` formatting.
- Follow EAFP: handle exceptions rather than checking conditions up front.
- Write Google-style docstrings for every public function and method.
- Validate request bodies with Pydantic models.
- Embrace idiomatic Python like comprehensions, generators, and decorators.

---

## Ignore

Treat everything in `.gitignore` as off-limits to read or edit. On top of
that, never open:

- Secrets and `.env` files
- Large data files unrelated to the current task
- Vendored or generated code

---

##  Repository Overview

This is a **Python monorepo** containing multiple protocol-to-MQTT bridge services
and a shared common library.

Target layout (partly aspirational). All four bridges (`modbus2mqtt/`, `mbus2mqtt/`,
`sml2mqtt/`, `so2mqtt/`) and `common/` exist today; `docker/` and `pyproject.toml` are
not yet created.

```
iot-mqtt-bridges/
 common/              # Shared library: mqttclient, logger, BaseConfig
 modbus2mqtt/         # Modbus TCP/RTU → MQTT bridge (implemented)
 mbus2mqtt/           # M-Bus (heat/water meters) → MQTT bridge (implemented)
 sml2mqtt/            # SML (smart meter language) → MQTT bridge (implemented)
 so2mqtt/             # S0 pulse counter → MQTT bridge (implemented)
 docker/              # Per-service Dockerfiles (planned)
 docker-compose.yml   # (planned)
 pyproject.toml       # (planned)
```

---

## Architecture Principles

- **Common library first**: Shared logic (MQTT, logging, config) lives in `common/`.
  Never duplicate these in individual bridges.
- **Bridge class**: Each bridge exposes a single coordinator class (e.g.
  `Modbus2Mqtt`) that owns its lifecycle and implements:
  - `load_config() -> dict`
  - `start_logging()`
  - `start_mqtt()`
  - `connect_source()`
  - `read_data() -> dict`
  - `map_to_topics(data: dict) -> list[tuple[str, str]]`
  - `publish(topics)`
  - `run()` / `stop()`
  > A shared `BaseBridge` ABC is a future goal but does not exist yet. Until it
  > lands, bridges define these methods directly on their own class.
- **Config-driven**: All runtime parameters come from a per-bridge YAML file.
  No hardcoded IPs, ports, topics, or credentials anywhere in the code.
- **Bridge owns its lifecycle**: The bridge class loads its own config and starts
  logging and MQTT (`start_logging()`, `start_mqtt()`). `main()` is a thin launcher
  that constructs the bridge with a config file path and calls `run()`.
- **No global state**: Avoid module-level mutable state. Use class instances.

---

##  Common Library `common/`

### `common/mqtt/mqtt_client.py`
- Wraps `paho-mqtt` with connect/publish/subscribe/disconnect lifecycle plus a
  retained last-will status.
- Class is `mqttclient`. Constructor takes connection params directly (broker,
  port, last_will_topic, etc.); there is no `MqttConfig` dataclass yet.
- Exposes: `connect()`, `publish(topic, message, qos, retain)`, `subscribe()`,
  `disconnect()`, `stateUpdate(state)`.
- Do NOT add protocol-specific logic here.

### `common/config/base_config.py`
- `BaseConfig` loads a YAML config file, resolving paths relative to the project
  root. Usage: `BaseConfig.load("modbus2mqtt/config/<file>.yaml").data`.
- ENV variable overrides are a future goal and not implemented yet.

### `common/logging/app_logger.py`
- `AppLogger().setup(name, loggingmode, level, ...)` configures logging via
  `dictConfig` for CONSOLE, SYSLOG, or FILE modes and returns a logger.
- Some existing modules still call
  `logging.getLogger(...)` directly; new code should prefer this setup.

---

## ðŸŒ‰ Bridge Conventions

Each bridge follows this structure (as scaffolded for `modbus2mqtt`):

```
<protocol>2mqtt/
├── __init__.py
├── main.py               # Thin launcher: main() builds the bridge class and calls run()
├── <protocol>2mqtt class  # Coordinator, e.g. Modbus2Mqtt, defined in main.py
├── <protocol>_reader.py  # Protocol-specific connection & raw data reading
├── <protocol>_mapper.py  # Pure functions: transform raw data → topics/payloads
└── config/
    └── <protocol>2mqtt_*.yaml
```

### Rules
- `main.py` is the ONLY entry point and must define a `main()` function. `main()`
  stays thin: it builds the bridge coordinator class and calls `run()`. Config
  loading, logging, and MQTT startup live on the bridge class.
- `<protocol>_reader.py` handles only I/O — no MQTT, no logging business logic.
- `<protocol>_mapper.py` handles only data transformation; pure functions preferred.
- Current published topic contract: `{PUBLISH}/{device_id}` with a JSON body of
  `{register_name: {VALUE, UNIT}}`. (The `.../{metric}` per-topic layout is a
  future goal, not what the code does today.)

---

## Configuration YAML Schema

Every bridge config MUST include these top-level keys:

```yaml
mqtt:
  host: string          # MQTT broker hostname or IP
  port: int             # Default 1883
  client_id: string     # Unique per bridge instance
  base_topic: string    # e.g. "plant/floor1"
  username: string|null
  password: string|null
  use_tls: bool         # Default false

poll_interval: int      # Seconds between read cycles (default: 5)
log_level: string       # DEBUG | INFO | WARNING | ERROR (default: INFO)
log_file: string|null   # Optional path for rotating log file
```

Protocol-specific sections (e.g. `modbus:`, `mbus:`) are added below these.
Passwords are not in the configuration file; they should be provided via environment variables. The YAML file should reference these environment variables instead. 

---

## Docker Guidelines

- Each bridge has its own Dockerfile in `docker/<bridge>.Dockerfile`.
- Base image: `python:3.12-slim`
- Config is mounted via Docker volume never baked into the image.
- No credentials in Dockerfiles or `docker-compose.yml` â€” use `.env` files.
- All services use `restart: unless-stopped`.

---

## ðŸ§ª Testing

- Tests live in `tests/<bridge>/` mirroring the source structure.
- Use `pytest` with `pytest-mock`.
- `MqttClient` must be mocked in all bridge tests â€” never connect to a real broker.
- Target minimum coverage: **80%** for `common/`, **60%** for individual bridges.
- Run tests: `pytest tests/ -v --cov=common --cov=modbus2mqtt ...`

---

## ðŸ”’ Security Rules

- NEVER commit secrets, passwords, or API keys.
- NEVER hardcode IP addresses or hostnames.
- NEVER disable TLS verification (`tls_insecure_set(True)`) without a comment explaining why.
- Credentials always come from YAML config or environment variables.

---

##  Code Style

- Python **3.12+** — use modern type hints (`str | None`, `list[tuple[...]]`).
- Follow **PEP 8**. Max line length: **100 characters**.
- Use **dataclasses** for config/data transfer objects.
- Use **f-strings** for all string formatting.
- No bare `except:` clauses â€” always catch specific exceptions.
- All public methods and classes must have **docstrings**.


---

## Do NOT

- Do NOT add `paho-mqtt` client logic outside of `common/mqtt/mqtt_client.py`.
- Do NOT use `print()` in new code — use `AppLogger` from `common/logging/app_logger.py`.
- Do NOT use `time.sleep()` in the bridge `run()` loop without checking the stop
  condition first.
- Do NOT create new top-level packages without updating `pyproject.toml`.
- Do NOT use synchronous blocking calls without documenting the threading model.

---

## âœ… Checklist Before Committing

- [ ] Bridge coordinator class implements its lifecycle methods (load_config,
      start_logging, start_mqtt, connect_source, read_data, map_to_topics, publish,
      run/stop)
- [ ] New config keys documented in the YAML schema section above
- [ ] No hardcoded values â€” everything in YAML or ENV
- [ ] `AppLogger` from `common/logging/app_logger.py` used (not `print`)
- [ ] Unit tests added or updated
- [ ] `ruff check .` passes with no errors
- [ ] `docker-compose up <service>` tested locally if Dockerfile was changed

---

## ðŸ“š Key Dependencies

| Package         | Purpose                          | Min Version |
|-----------------|----------------------------------|-------------|
| `paho-mqtt`     | MQTT client                      | 2.0         |
| `PyYAML`        | Config file parsing              | 6.0         |
| `pyserial`      | Serial port access (M-Bus, SML, S0) | 3.5      |
| `pymodbus`      | Modbus TCP/RTU protocol          | 3.6         |
| `pyMeterBus`    | M-Bus protocol (imported as `meterbus`) | 0.8.4 |
| `smllib`        | SML (smart meter) parsing        | 1.2         |
| `pytest`        | Testing framework                | 8.0         |
| `pytest-mock`   | Mocking in tests                 | 3.12        |
| `ruff`          | Linting and formatting           | 0.4         |

---

*Last updated: 2026-08-28 â€” keep this file in sync with architectural changes.*