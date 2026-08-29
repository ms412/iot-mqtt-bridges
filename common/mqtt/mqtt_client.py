#!/usr/bin/env python3
"""Thin wrapper around paho-mqtt with lifecycle, LWT, and reconnect handling."""

import json
import logging
import threading
import time
from typing import Callable

import paho.mqtt.client as mqtt


class MqttClient:
    """Manage an MQTT connection: connect, publish, subscribe, and last-will.

    This is the only place paho-mqtt is used directly. It owns the network
    loop, retained online/offline status, JSON encode/decode, topic callbacks,
    and automatic reconnect.
    """

    LOG_LEVELS = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
        keepalive: int = 60,
        last_will_topic: str | None = None,
        last_will_message: str | dict | list = "OFFLINE",
        last_will_qos: int = 0,
        last_will_retain: bool = True,
        auto_json: bool = True,
        log_name: str = "MqttClient",
        log_level: int | str = logging.INFO,
    ) -> None:
        """Initialize the client and configure the last will.

        Args:
            broker: Broker hostname or IP address.
            port: Broker port.
            client_id: Optional MQTT client id.
            username: Optional username for authentication.
            password: Optional password for authentication.
            keepalive: Keepalive interval in seconds.
            last_will_topic: Topic for the retained online/offline status.
            last_will_message: Payload published as the last will.
            last_will_qos: QoS for the last will.
            last_will_retain: Whether the last will is retained.
            auto_json: When True, dict/list payloads are JSON-encoded on publish
                and incoming payloads are JSON-decoded.
            log_name: Base logger name.
            log_level: Log level as an int or a level name string.
        """
        if isinstance(log_level, str):
            log_level = self.LOG_LEVELS.get(log_level.upper(), logging.INFO)

        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{log_name}.{_lib_name}.{self.__class__.__name__}")
        self._log.setLevel(log_level)

        if not self._log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._log.addHandler(handler)

        self._broker = broker
        self._port = port
        self._keepalive = keepalive
        self._callback_topic_store: dict = {}
        self._callback_lost_connection: Callable | None = None
        self._auto_json = auto_json
        self._lock = threading.Lock()

        self.client = mqtt.Client(client_id=client_id, clean_session=True, userdata=None)

        if username and password:
            self.client.username_pw_set(username, password)

        if last_will_topic and last_will_message:
            self._last_will_topic = last_will_topic
            self._last_will_message = last_will_message
            self._last_will_retain = last_will_retain
            self._last_will_qos = last_will_qos
            self._set_last_will()

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._log.debug("Created MqttClient object")

    def _set_last_will(self) -> None:
        """Register the last-will message with the paho client.

        Returns:
            None.
        """
        self._log.info("Setting Last Will on '%s'", self._last_will_topic)
        if isinstance(self._last_will_message, (dict, list)) and self._auto_json:
            self._last_will_message = json.dumps(self._last_will_message)
        self.client.will_set(
            self._last_will_topic,
            payload=self._last_will_message,
            qos=self._last_will_qos,
            retain=self._last_will_retain,
        )

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        """Handle a broker connection: publish ONLINE and re-subscribe topics.

        Args:
            client: The paho client instance.
            userdata: User data set on the client (unused).
            flags: Response flags from the broker.
            rc: Connection result code (0 means success).

        Returns:
            None.
        """
        if rc == 0:
            self._log.info("Connected to %s:%s", self._broker, self._port)
            client.publish(
                topic=self._last_will_topic,
                payload="ONLINE",
                qos=self._last_will_qos,
                retain=self._last_will_retain,
            )
            with self._lock:
                for topic in self._callback_topic_store:
                    client.subscribe(topic)
                    self._log.info("Re-subscribed to %s", topic)
        else:
            self._log.error("Connection failed with code %s", rc)

    def _on_disconnect(self, client: mqtt.Client, userdata: object, rc: int) -> None:
        """Handle a disconnect and trigger reconnect when unexpected.

        Args:
            client: The paho client instance.
            userdata: User data set on the client (unused).
            rc: Disconnect result code (0 means a clean disconnect).

        Returns:
            None.
        """
        self._log.warning("Disconnected from broker")
        if rc != 0:
            self._log.warning("Unexpected disconnect - attempting reconnect")
            if self._callback_lost_connection:
                try:
                    self._callback_lost_connection()
                except Exception as exc:
                    self._log.exception("Error in connection lost callback: %s", exc)
            self._reconnect()

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        """Dispatch an incoming message to its registered topic callback.

        Args:
            client: The paho client instance.
            userdata: User data set on the client (unused).
            msg: The received MQTT message.

        Returns:
            None.
        """
        payload: object = msg.payload.decode(errors="ignore")
        topic = msg.topic

        if self._auto_json:
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass

        self._log.debug("Received message on %s: %s", topic, payload)
        with self._lock:
            callback = self._callback_topic_store.get(topic)
        if callback:
            try:
                callback(topic, payload)
            except Exception as exc:
                self._log.exception("Error in callback for %s: %s", topic, exc)

    def connect(self) -> None:
        """Connect to the broker and start the network loop.

        Returns:
            None.
        """
        self._log.info("Connecting to broker %s:%s", self._broker, self._port)
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        with self._lock:
            self.client.connect(self._broker, int(self._port), self._keepalive)
        self.client.loop_start()

    def disconnect(self) -> None:
        """Stop the network loop and disconnect cleanly.

        Returns:
            None.
        """
        self._log.info("Disconnecting")
        with self._lock:
            self.client.loop_stop()
            self.client.disconnect()

    def subscribe(self, topic: str, callback: Callable) -> None:
        """Subscribe to a topic and register a message callback.

        Args:
            topic: The topic filter to subscribe to.
            callback: Callable invoked as ``callback(topic, payload)``.

        Returns:
            None.
        """
        with self._lock:
            self._log.info("Subscribing to topic '%s'", topic)
            self._callback_topic_store[topic] = callback
            self.client.subscribe(topic)

    def publish(self, topic: str, message: str | dict | list, qos: int = 0,
                retain: bool = False) -> None:
        """Publish a message, JSON-encoding dict/list payloads when enabled.

        Args:
            topic: Destination topic.
            message: Payload to publish; dict/list are JSON-encoded if
                ``auto_json`` is enabled.
            qos: Quality of service level.
            retain: Whether the broker should retain the message.

        Returns:
            None.
        """
        if isinstance(message, (dict, list)) and self._auto_json:
            try:
                message = json.dumps(message)
            except Exception as exc:
                self._log.exception("JSON encoding error for %s: %s", topic, exc)

        with self._lock:
            self._log.debug("Publishing to %s: %s", topic, message)
            self.client.publish(topic, message, qos=qos, retain=retain)

    def set_connection_lost_callback(self, callback: Callable) -> None:
        """Register a callback invoked on an unexpected disconnect.

        Args:
            callback: Zero-argument callable invoked when the connection drops.

        Returns:
            None.
        """
        with self._lock:
            self._callback_lost_connection = callback

    def state_update(self, state: bool) -> bool:
        """Update the retained last-will payload for the current online state.

        Args:
            state: True publishes ONLINE, False publishes OFFLINE.

        Returns:
            True when the state update was applied, False when no last-will
            topic is configured.
        """
        if not hasattr(self, "_last_will_topic"):
            self._log.warning("No last will topic configured; skipping state update.")
            return False

        self.client.will_set(
            self._last_will_topic,
            payload="ONLINE" if state else "OFFLINE",
            qos=self._last_will_qos,
            retain=self._last_will_retain,
        )
        return True

    def _reconnect(self) -> None:
        """Reconnect to the broker, retrying until successful.

        Returns:
            None.
        """
        while True:
            try:
                with self._lock:
                    self.client.reconnect()
                    self._set_last_will()
                self._log.info("Reconnected successfully")
                break
            except Exception as exc:
                self._log.warning("Reconnect failed: %s", exc)
                time.sleep(5)
