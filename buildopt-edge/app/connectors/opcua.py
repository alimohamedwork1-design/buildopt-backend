from app.connectors.bacnet import _PlaceholderConnector


class OpcUaConnector(_PlaceholderConnector):
    def __init__(self) -> None:
        super().__init__("opcua", "PLANNED")
