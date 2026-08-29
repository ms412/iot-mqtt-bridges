#!/usr/bin/env python3
# "THE BEER-WARE LICENSE" (Revision 42): see the LICENSE file. As long as you
# retain this notice you can do whatever you want with this stuff.
"""Entry point and coordinator for the so2mqtt bridge."""

import sys
import time

from common.config.base_config import BaseConfig
from common.logging.app_logger import AppLogger
from common.mqtt.mqtt_client import MqttClient
from so2mqtt import so_mapper
from so2mqtt.so_reader import So0Reader

__APP__ = "so2mqtt"
DEFAULT_CONFIG = "so2mqtt/config/so2mqtt.yaml"


class So2Mqtt:
    """Coordinate reading S0 pulse-counter data and publishing it to MQTT.

    The bridge loads its own configuration, starts logging and MQTT, and
    delegates protocol I/O to :class:`So0Reader` and payload transformation to
    :mod:`so2mqtt.so_mapper`.
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
        self._reader: So0Reader | None = None
        self._running = False

    def load_config(self) -> dict:
        """Load and cache the bridge configuration via :class:`BaseConfig`.

        Returns:
            The parsed configuration (LOGGING, BROKER, S0 sections).
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
            filename=log_config.get("LOGFILE", "so2mqtt.log"),
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
        """Open the S0 serial interface(s).

        Returns:
            None.
        """
        self._reader = So0Reader(self._config.get("S0", {}))
        self._reader.connect()
        self._log.info("S0 source connected")

    def read_data(self) -> dict:
        """Query every interface and map each channel to a payload.

        Returns:
            Mapping of interface name to ``{channel: {S0, S0_raw}}`` dicts.
        """
        raw = self._reader.read_all()
        processed: dict = {}
        for interface, field_list in raw.items():
            interface_config = self._reader.interface_config(interface)
            processed[interface] = so_mapper.process_interface(interface_config, field_list)
            self._log.debug("Interface %s: %d channel(s)", interface, len(processed[interface]))
        return processed

    def map_to_topics(self, data: dict) -> list[tuple[str, str]]:
        """Transform processed S0 data into (topic, payload) pairs.

        Args:
            data: Processed per-interface readings produced by :meth:`read_data`.

        Returns:
            List of (topic, json_payload) tuples ready to publish.
        """
        base = self._config.get("BROKER", {}).get("PUBLISH", "SERIAL2MQTT")
        return so_mapper.map_to_topics(data, base)

    def publish_data(self, topics: list[tuple[str, str]]) -> None:
        """Publish each (topic, payload) pair (retained) via the MQTT client.

        Args:
            topics: Publish pairs produced by :meth:`map_to_topics`.

        Returns:
            None.
        """
        for topic, payload in topics:
            self._log.debug("Publishing to %s: %s", topic, payload)
            self._mqtt.publish(topic, payload, retain=True)
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

        s0 = self._config.get("S0", {})
        startup_delay = int(s0.get("STARTUP_DELAY", 5))
        update_interval = int(s0.get("UPDATE_INTERVAL", 15))

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
    bridge = So2Mqtt(configfile)
    bridge.run()


if __name__ == "__main__":
    main()
