from typing import Callable, Optional


class MQTTClient:
    def __init__(
        self,
        broker: str,
        port: int,
        username: str,
        password: str,
        demo_mode: bool = True,
    ) -> None:
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.demo_mode = demo_mode
        self._client = None
        self._connected = False

        if not demo_mode:
            try:
                import paho.mqtt.client as mqtt

                self._client = mqtt.Client()
                if username:
                    self._client.username_pw_set(username, password)
                self._client.connect(broker, port, keepalive=60)
                self._connected = True
            except Exception:
                self._client = None
                self._connected = False

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        return "connected" if self._connected else "disconnected"

    def publish(self, topic: str, payload: str) -> bool:
        if self.demo_mode:
            return True
        if self._client is None:
            return False
        try:
            result = self._client.publish(topic, payload)
            return result.rc == 0
        except Exception:
            return False

    def subscribe(self, topic: str, callback: Callable) -> bool:
        if self.demo_mode:
            return True
        if self._client is None:
            return False
        try:
            self._client.subscribe(topic)
            self._client.on_message = callback
            return True
        except Exception:
            return False
