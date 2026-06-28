from typing import Any, Dict, List, Optional


class BACnetClient:
    def __init__(self, ip: str, port: int, demo_mode: bool = True) -> None:
        self.ip = ip
        self.port = port
        self.demo_mode = demo_mode
        self._bacnet = None

        if not demo_mode:
            try:
                import BAC0

                self._bacnet = BAC0.lite(ip=f"{ip}/{port}")
            except Exception:
                self._bacnet = None

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if self._bacnet is None:
            return "disconnected"
        return "connected"

    def read_points(self, points: List[str]) -> Dict[str, Any]:
        if self.demo_mode:
            return {point: 0.0 for point in points}
        results: Dict[str, Any] = {}
        if self._bacnet is None:
            return results
        for point in points:
            try:
                results[point] = self._bacnet.read(point)
            except Exception:
                results[point] = None
        return results
