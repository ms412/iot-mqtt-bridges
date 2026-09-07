#!/usr/bin/env python3
"""Sungrow WiNet-S WebSocket I/O for the sungrow2mqtt bridge.

Adapted from github.com/ms412/sungrow2mqtt. Connects to a Sungrow inverter's
WiNet-S dongle over a WebSocket, authenticates, and reads per-device real-time
and direct measurement data. Contains no MQTT logic.
"""

import json
import logging
import ssl
import time

import websocket

__APP__ = "sungrow2mqtt"


class SungrowReader:
    """Read live device data from a Sungrow inverter over WebSocket.

    The reader authenticates against the WiNet-S dongle, lists devices, and
    fetches each device's ``real`` and ``direct`` measurement lists.
    """

    def __init__(self, sungrow_config: dict) -> None:
        """Initialize the reader.

        Args:
            sungrow_config: The SUNGROW section of the bridge config.
        """
        _lib_name = str(__name__.rsplit(".", 1)[-1])
        self._log = logging.getLogger(f"{__APP__}.{_lib_name}.{self.__class__.__name__}")

        self._config = sungrow_config or {}
        self._host = str(self._config.get("HOST", "127.0.0.1"))
        self._port = int(self._config.get("PORT", 443))
        self._username = str(self._config.get("USERNAME", "user"))
        self._password = str(self._config.get("PASSWORD", ""))
        self._lang = str(self._config.get("LANG", "en_us"))
        self._timeout = int(self._config.get("TIMEOUT", 30))

        self._ws = None
        self._token = None
        self._ws_url = f"wss://{self._host}:{self._port}/ws/home/overview"

    def connect(self) -> None:
        """Open the WebSocket connection and authenticate.

        The WiNet-S dongle uses a self-signed certificate, so TLS verification
        is disabled (``ssl.CERT_NONE``); this connection is expected to run on
        the local LAN only.

        Returns:
            None.
        """
        self._log.info("Connecting to %s", self._ws_url)
        ssl_options = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
        self._ws = websocket.create_connection(
            self._ws_url,
            timeout=self._timeout,
            header=[f"Origin: https://{self._host}"],
            sslopt=ssl_options,
        )
        self._authenticate()
        self._log.info("Sungrow WebSocket connected and authenticated")

    def _authenticate(self) -> None:
        """Perform the connect + login handshake and capture the token.

        Returns:
            None.
        """
        self._send({"lang": self._lang, "token": "", "service": "connect"})
        response = self._receive_json()
        self._token = (response or {}).get("token", "") if response else ""

        self._send({
            "lang": self._lang,
            "service": "login",
            "passwd": self._password,
            "username": self._username,
            "token": self._token,
        })
        response = self._receive_json()
        if response and response.get("result_code") == 1 and "result_data" in response:
            self._token = response["result_data"].get("token", self._token)
            self._log.info("Login successful")
        else:
            self._log.warning("Login response invalid: %s", response)

    def _send(self, message: dict) -> None:
        """Send a JSON message over the WebSocket.

        Args:
            message: The message payload to serialize and send.

        Returns:
            None.
        """
        self._ws.send(json.dumps(message))

    def _receive_json(self) -> dict | None:
        """Receive and parse a single JSON response.

        Returns:
            The parsed response dict, or None on timeout/parse failure.
        """
        time.sleep(1)
        try:
            raw = self._ws.recv()
            if raw:
                return json.loads(raw)
        except (ConnectionResetError, OSError, websocket.WebSocketException) as exc:
            self._log.warning("WebSocket receive failed: %s", exc)
            self.close()
        except json.JSONDecodeError as exc:
            self._log.error("Failed to parse JSON response: %s", exc)
        return None

    def _service_list(self, service: str, device_id: str) -> list:
        """Request a per-device service list (``real`` or ``direct``).

        Args:
            service: The WiNet-S service name.
            device_id: The device id to query.

        Returns:
            The ``list`` portion of ``result_data``, or an empty list.
        """
        self._send({
            "lang": self._lang,
            "token": self._token,
            "service": service,
            "dev_id": str(device_id),
            "time123456": int(time.time() * 1000),
        })
        response = self._receive_json()
        if response and response.get("result_code") == 1:
            return response.get("result_data", {}).get("list", [])
        self._log.warning("%s request failed for device %s: %s", service, device_id, response)
        return []

    def read_all(self) -> list[dict]:
        """List devices and attach their real and direct measurement lists.

        Returns:
            A list of device dicts, each with ``REAL`` and ``DIRECT`` lists.
        """
        self._send({
            "lang": self._lang,
            "token": self._token,
            "service": "devicelist",
            "type": "0",
            "is_check_token": "1",
        })
        response = self._receive_json()
        if not (response and response.get("result_code") == 1):
            self._log.warning("Device list request failed: %s", response)
            return []

        devices = response.get("result_data", {}).get("list", [])
        for device in devices:
            device_id = device.get("dev_id")
            device["REAL"] = self._service_list("real", device_id)
            device["DIRECT"] = self._service_list("direct", device_id)
        self._log.info("Retrieved %d device(s) from WiNet-S", len(devices))
        return devices

    def ping(self) -> bool:
        """Send a keepalive ping.

        Returns:
            True when the inverter acknowledges the ping, False otherwise.
        """
        try:
            self._send({"lang": self._lang, "service": "ping", "token": self._token})
            response = self._receive_json()
        except (ConnectionResetError, OSError, websocket.WebSocketException) as exc:
            self._log.warning("Ping failed: %s", exc)
            return False
        return bool(response and response.get("result_code") == 1)

    def close(self) -> None:
        """Close the WebSocket connection if it is open.

        Returns:
            None.
        """
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._log.info("Sungrow WebSocket closed")

    def reconnect(self) -> None:
        """Close and re-open the WebSocket connection.

        Returns:
            None.
        """
        self.close()
        time.sleep(5)
        self.connect()
