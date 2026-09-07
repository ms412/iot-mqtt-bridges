#!/usr/bin/env python3
# "THE BEER-WARE LICENSE" (Revision 42): see the LICENSE file. As long as you
# retain this notice you can do whatever you want with this stuff.
"""Entry point and coordinator for the sungrow2mqtt bridge."""

import os
import re
import sys
import time

from common.config.base_config import BaseConfig
from common.logging.app_logger import AppLogger
from common.mqtt.mqtt_client import MqttClient
from sungrow2mqtt import sungrow_mapper
from sungrow2mqtt.sungrow_reader import SungrowReader

__APP__ = "sungrow2mqtt"
DEFAULT_CONFIG = "sungrow2mqtt/config/sungrow2mqtt.yaml"

_ENV_REF = re.compile(r"^\$\{([^}]+)\}$")


def _resolve_env(value: object) -> object:
    """Resolve a ``${VAR}`` reference against the environment.

    Args:
        value: A config value that may be a ``${VAR}`` placeholder.

    Returns:
        The environment value when ``value`` is a ``${VAR}`` reference,
        otherwise ``value`` unchanged.
    """
    if isinstance(value, str):
        match = _ENV_REF.match(value.strip())
        if match:
            return os.environ.get(match.group(1), "")
    return value


class Sungrow2Mqtt:
    """Coordinate reading Sungrow inverter data and publishing it to MQTT.

    The bridge loads its own configuration, starts logging and MQTT, and
    delegates WebSocket I/O to :class:`SungrowReader` and payload transformation
    to :mod:`sungrow2mqtt.sungrow_mapper`.
    """

    def __init__(self, configfile: str) -> None:
        """Initialize the bridge.

        Args:
            configfile: Path to the bridge config, relative to the project root.
        """
        self._configfile = configfile
        self._config: dict = {}
        self._log = None
        self._mqtt: MqttClient | None = None
        self._reader: SungrowReader | None = None
        self._running = False

    def load_config(self) -> dict:
        """Load and cache the bridge configuration via :class:`BaseConfig`.

        Any ``${VAR}`` values in the SUNGROW section are resolved from the
        environment (used for the inverter password).

        Returns:
            The parsed configuration (LOGGING, BROKER, SUNGROW sections).
        """
        self._config = BaseConfig.load(self._configfile).data
        sungrow = self._config.get("SUNGROW", {})
        for key, value in sungrow.items():
            sungrow[key] = _resolve_env(value)
        return self._config

    def start_logging(self):
        """Configure the application logger from the LOGGING config section.

        Returns:
            The configured ``logging.Logger`` instance.
        """
        log_config = self._config.get("LOGGING", {})
        self._log = AppLogger().setup(
            name=__APP__,
            loggingmode=log_config.get("LOGMODE", "CONSOLE"),
            level=log_config.get("LOGLEVEL", "INFO"),
            filename=log_config.get("LOGFILE", "sungrow2mqtt.log"),
        )
        return self._log

    def start_mqtt(self) -> MqttClient:
        """Create and connect the MQTT client from the BROKER config section.

        Returns:
            A connected :class:`MqttClient` instance.
        """
        broker = self._config.get("BROKER", {})
        log_config = self._config.get("LOGGING", {})
        self._mqtt = MqttClient(
            broker=broker.get("BROKER", "127.0.0.1"),
            port=int(broker.get("PORT", 1883)),
            last_will_topic=broker.get("LWT_TOPIC"),
            last_will_message="OFFLINE",
            last_will_retain=True,
            last_will_qos=1,
            log_name=__APP__,
            log_level=log_config.get("LOGLEVEL", "INFO"),
        )
        self._mqtt.connect()
        return self._mqtt

    def connect_source(self) -> None:
        """Open the Sungrow WebSocket connection.

        Returns:
            None.
        """
        self._reader = SungrowReader(self._config.get("SUNGROW", {}))
        self._reader.connect()
        self._log.info("Sungrow source connected")

    def read_data(self) -> list[dict]:
        """Read the current device list with real and direct data.

        Returns:
            The device list produced by the reader.
        """
        devices = self._reader.read_all()
        self._log.debug("Read %d device(s)", len(devices))
        return devices

    def map_to_topics(self, data: list[dict]) -> list[tuple[str, str]]:
        """Transform device data into (topic, payload) pairs.

        Args:
            data: The device list produced by :meth:`read_data`.

        Returns:
            List of (topic, json_payload) tuples ready to publish.
        """
        base = self._config.get("BROKER", {}).get("PUBLISH", "SUNGROW")
        return sungrow_mapper.map_to_topics(data, base)

    def publish_data(self, topics: list[tuple[str, str]]) -> None:
        """Publish each (topic, payload) pair via the MQTT client.

        Args:
            topics: Publish pairs produced by :meth:`map_to_topics`.

        Returns:
            None.
        """
        for topic, payload in topics:
            self._log.debug("Publishing to %s: %s", topic, payload)
            self._mqtt.publish(topic, payload)
        self._log.info("Published %d topic(s)", len(topics))

    def run(self) -> None:
        """Run the full bridge lifecycle until interrupted.

        Returns:
            None.
        """
        self.load_config()
        self.start_logging()
        self._log.info("Startup, %s bridge", __APP__)
        self._log.debug("Configuration loaded from %s", self._configfile)

        sungrow = self._config.get("SUNGROW", {})
        startup_delay = int(sungrow.get("STARTUP_DELAY", 5))
        update_interval = int(sungrow.get("UPDATE_INTERVAL", 10))

        self.start_mqtt()
        self.connect_source()

        self._log.info("Polling every %ds (startup delay %ds)", update_interval, startup_delay)
        time.sleep(startup_delay)

        self._running = True
        try:
            while self._running:
                try:
                    data = self.read_data()
                    self.publish_data(self.map_to_topics(data))
                    self._mqtt.state_update(state=True)
                    if not self._reader.ping():
                        self._log.warning("Ping failed; reconnecting")
                        self._reader.reconnect()
                except (OSError, ConnectionError) as exc:
                    self._log.warning("WebSocket cycle failed; reconnecting: %s", exc)
                    self._reader.reconnect()
                if not self._running:
                    break
                time.sleep(update_interval)
        except KeyboardInterrupt:
            self._log.info("Interrupted; shutting down")
        except Exception as exc:
            self._log.exception("Unexpected error in polling loop: %s", exc)
        finally:
            self.stop()

    def stop(self) -> None:
        """Signal the polling loop to stop and release resources.

        Returns:
            None.
        """
        self._running = False
        if self._log is not None:
            self._log.info("Stopping %s bridge", __APP__)
        if self._reader is not None:
            self._reader.close()
        if self._mqtt is not None:
            self._mqtt.disconnect()


def main() -> None:
    """Construct the bridge and run it.

    Returns:
        None.
    """
    configfile = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG
    bridge = Sungrow2Mqtt(configfile)
    bridge.run()


if __name__ == "__main__":
    main()
