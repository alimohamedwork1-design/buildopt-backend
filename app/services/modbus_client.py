from typing import Any, Dict, List, Optional


class ModbusClient:
    def __init__(self, host: str, port: int, demo_mode: bool = True) -> None:
        self.host = host
        self.port = port
        self.demo_mode = demo_mode
        self._client = None

        if not demo_mode:
            try:
                from pymodbus.client import ModbusTcpClient

                self._client = ModbusTcpClient(host, port=port)
                self._client.connect()
            except Exception:
                self._client = None

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if self._client is None or not self._client.connected:
            return "disconnected"
        return "connected"

    def read_registers(self, address: int, count: int = 1) -> List[int]:
        if self.demo_mode:
            return [0] * count
        if self._client is None:
            return []
        try:
            result = self._client.read_holding_registers(address, count=count)
            return list(result.registers)
        except Exception:
            return []
