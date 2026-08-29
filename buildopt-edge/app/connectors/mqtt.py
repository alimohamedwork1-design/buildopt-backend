from app.connectors.bacnet import _PlaceholderConnector


class MqttConnector(_PlaceholderConnector):
    def __init__(self) -> None:
        super().__init__("mqtt", "PLANNED")
