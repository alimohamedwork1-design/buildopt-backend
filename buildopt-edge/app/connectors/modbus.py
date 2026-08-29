from app.connectors.bacnet import _PlaceholderConnector


class ModbusConnector(_PlaceholderConnector):
    def __init__(self) -> None:
        super().__init__("modbus", "BETA")
