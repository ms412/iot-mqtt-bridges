#!/usr/bin/env python3
# "THE BEER-WARE LICENSE" (Revision 42): see the LICENSE file. As long as you
# retain this notice you can do whatever you want with this stuff.
"""Entry point and coordinator for the mbus2mqtt bridge."""

import sys
import time

from common.config.base_config import BaseConfig
from common.logging.app_logger import AppLogger
from common.mqtt.mqtt_client import MqttClient
from mbus2mqtt import mbus_mapper
from mbus2mqtt.mbus_reader import MbusReader

__APP__ = "mbus2mqtt"
DEFAULT_CONFIG = "mbus2mqtt/config/mbus2mqtt.yaml"


class Mbus2Mqtt:
    """Coordinate reading M-Bus data and publishing it to MQTT.

    The bridge loads its own configuration, starts logging and MQTT, and
    delegates protocol I/O to :class:`MbusReader` and payload transformation to
    :mod:`mbus2mqtt.mbus_mapper`.
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
        self._reader: MbusReader | None = None
        self._running = False

    def load_config(self) -> dict:
        """Load and cache the bridge configuration via :class:`BaseConfig`.

        Returns:
            The parsed configuration (LOGGING, BROKER, MBUS sections).
        """
        self._config = BaseConfig.load(self._configfile).data
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
            filename=log_config.get("LOGFILE", "mbus2mqtt.log"),
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
        """Open the M-Bus serial interface.

        Returns:
            None.
        """
        self._reader = MbusReader(self._config.get("MBUS", {}))
        self._reader.connect()
        self._log.info("M-Bus source connected")

    def read_data(self) -> dict:
        """Read every configured slave and map it to a payload per slave.

        Returns:
            Mapping of slave id to processed ``{metric: value}`` dicts.
        """
        raw = self._reader.read_all()
        processed: dict = {}
        for slave_id, raw_value in raw.items():
            slave_config = self._reader.slave_config(slave_id)
            processed[slave_id] = mbus_mapper.map_slave(slave_config, raw_value)
            self._log.debug("Slave %s: %s", slave_id, processed[slave_id])
        return processed

    def map_to_topics(self, data: dict) -> list[tuple[str, str]]:
        """Transform processed slave data into (topic, payload) pairs.

        Args:
            data: Processed per-slave readings produced by :meth:`read_data`.

        Returns:
            List of (topic, json_payload) tuples ready to publish.
        """
        base = self._config.get("BROKER", {}).get("PUBLISH", "MBUS")
        return mbus_mapper.map_to_topics(data, base)

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

        mbus = self._config.get("MBUS", {})
        startup_delay = int(mbus.get("STARTUP_DELAY", 5))
        update_interval = int(mbus.get("UPDATE_INTERVAL", 30))

        self.start_mqtt()
        self.connect_source()

        self._log.info("Polling every %ds (startup delay %ds)", update_interval, startup_delay)
        time.sleep(startup_delay)

        self._running = True
        try:
            while self._running:
                data = self.read_data()
                self.publish_data(self.map_to_topics(data))
                self._mqtt.state_update(state=True)
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
    bridge = Mbus2Mqtt(configfile)
    bridge.run()


if __name__ == "__main__":
    main()
