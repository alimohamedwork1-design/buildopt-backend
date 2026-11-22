"""Read-only Modbus/TCP and RTU connector for BuildOpt Edge Hub V1.

Only function codes 01, 02, 03 and 04 are implemented. Never scans
unapproved addresses or writes any PLC registers. Real targets must be
explicitly enabled after site authorization.

Point format: `ir:0:u16:0.1`, `hr:4:f32be:1`, `di:0:bool:1`
All addresses are zero based; unit ID is explicit.
"""
from __future__ import annotations

import asyncio
import ipaddress
import math
import os
import socket
import struct
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.connectors.base import BuildingConnector, ConnectorError

_FUNCTION = {"coil": 1, "di": 2, "hr": 3, "ir": 4}
_WORDS = {"bool": 1, "u16": 1, "s16": 1, "u32be": 2, "u32ws": 2, "f32be": 2, "f32ws": 2}


class ModbusReadError(Exception):
    pass


@dataclass(frozen=True)
class ModbusPoint:
    area: str
    address: int
    kind: str
    scale: float = 1.0

    @classmethod
    def parse(cls, identifier: str) -> "ModbusPoint":
        parts = identifier.split(":")
        if len(parts) not in (3, 4):
            raise ValueError("expected area:zero_based_address:type[:scale]")
        area, address, kind = parts[:3]
        if area not in _FUNCTION or kind not in _WORDS:
            raise ValueError("unsupported Modbus area or value type")
        if (area in ("coil", "di")) != (kind == "bool"):
            raise ValueError("bit areas require bool; register areas require numeric types")
        if not address.isdecimal() or not 0 <= int(address) <= 65536 - _WORDS[kind]:
            raise ValueError("out-of-range address")
        factor = float(parts[3]) if len(parts) == 4 else 1.0
        if not math.isfinite(factor):
            raise ValueError("invalid scale")
        return cls(area, int(address), kind, factor)


def crc16(frame: bytes) -> int:
    crc = 0xFFFF
    for byte in frame:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc & 0xFFFF


def _read_exact(socket_or_stream: Any, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = socket_or_stream.recv(n - len(data))
        if not chunk:
            raise ModbusReadError("connection closed while reading response")
        data.extend(chunk)
    return bytes(data)


def _decode(point: ModbusPoint, raw: bytes) -> float | bool:
    if point.kind == "bool":
        if len(raw) != 1:
            raise ModbusReadError("missing bit payload")
        return bool(raw[0] & 1)
    if len(raw) != _WORDS[point.kind] * 2:
        raise ModbusReadError("unexpected register data length")
    if point.kind.endswith("ws"):
        raw = raw[2:] + raw[:2]
    dtype = point.kind[:3]
    fmt = {"u16": ">H", "s16": ">h", "u32": ">I", "f32": ">f"}[dtype]
    val = struct.unpack(fmt, raw)[0]
    scaled = val * point.scale
    if not math.isfinite(scaled):
        raise ModbusReadError("nonfinite telemetry")
    return scaled


class ModbusReadOnlyClient:
    def __init__(
        self, *, mode: str = "tcp", host: str = "127.0.0.1",
        port: int = 15020, unit: int = 1, serial_port: str = "",
        baudrate: int = 9600, parity: str = "N", stopbits: int = 1,
        timeout: float = 2.0,
    ):
        if mode not in ("tcp", "rtu") or not 1 <= unit <= 247:
            raise ValueError("invalid mode or Modbus unit ID")
        if not 0 < timeout <= 30:
            raise ValueError("invalid Modbus timeout")
        if mode == "rtu" and not serial_port:
            raise ValueError("RTU requires an explicit serial device")
        if parity not in ("N", "E", "O") or stopbits not in (1, 2):
            raise ValueError("invalid serial framing")
        if baudrate not in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200):
            raise ValueError("unsupported baudrate")
        self.mode, self.host, self.port, self.unit = mode, host, port, unit
        self.serial_port, self.baudrate, self.parity = serial_port, baudrate, parity
        self.stopbits, self.timeout = stopbits, timeout
        self._lock = threading.Lock()
        self._transaction_id = 0

    @staticmethod
    def _validate_pdu(payload: bytes, fc: int, count: int) -> bytes:
        if len(payload) < 2:
            raise ModbusReadError("short Modbus response")
        if payload[0] == (fc | 0x80):
            raise ModbusReadError(f"Modbus exception {payload[1]}")
        if payload[0] != fc:
            raise ModbusReadError("wrong function code")
        expected = (count + 7) // 8 if fc in (1, 2) else count * 2
        if payload[1] != expected or len(payload) != expected + 2:
            raise ModbusReadError("wrong response size or byte count")
        return payload[2:]

    def _tcp(self, req: bytes, count: int) -> bytes:
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        tid = self._transaction_id
        packet = struct.pack(">HHHB", tid, 0, len(req) + 1, self.unit) + req
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as stream:
            stream.settimeout(self.timeout)
            stream.sendall(packet)
            mbap = _read_exact(stream, 7)
            recv_tid, proto, length, unit = struct.unpack(">HHHB", mbap)
            if (recv_tid, proto, unit) != (tid, 0, self.unit) or not 2 <= length <= 254:
                raise ModbusReadError("invalid MBAP header")
            return self._validate_pdu(_read_exact(stream, length - 1), req[0], count)

    def _rtu(self, req: bytes, count: int) -> bytes:
        try:
            import serial
        except ImportError as exc:
            raise ModbusReadError("pyserial required for physical Modbus RTU") from exc
        body = bytes([self.unit]) + req
        packet = body + struct.pack("<H", crc16(body))
        with serial.Serial(
            self.serial_port, self.baudrate, parity=self.parity,
            stopbits=self.stopbits, timeout=self.timeout, write_timeout=self.timeout,
        ) as uart:
            uart.reset_input_buffer()
            uart.write(packet)
            header = uart.read(3)
            if len(header) != 3 or header[0] != self.unit:
                raise ModbusReadError("missing or wrong RTU response header")
            body_len = 0 if header[1] & 0x80 else header[2]
            if body_len > 250:
                raise ModbusReadError("oversized RTU response")
            tail = uart.read(body_len + 2)
            if len(tail) != body_len + 2:
                raise ModbusReadError("incomplete RTU response")
            response = header + tail
            if crc16(response[:-2]) != struct.unpack("<H", response[-2:])[0]:
                raise ModbusReadError("bad RTU CRC")
            return self._validate_pdu(response[1:-2], req[0], count)

    def read(self, point_id: str) -> float | bool:
        point = ModbusPoint.parse(point_id)
        count = _WORDS[point.kind]
        req = struct.pack(">BHH", _FUNCTION[point.area], point.address, count)
        with self._lock:
            raw = self._tcp(req, count) if self.mode == "tcp" else self._rtu(req, count)
        return _decode(point, raw)


def _loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(socket.gethostbyname(host)).is_loopback
    except OSError:
        return False


class ModbusConnector(BuildingConnector):
    read_only = True

    def __init__(self) -> None:
        mode = os.environ.get("MODBUS_MODE", "tcp").lower()
        host = os.environ.get("MODBUS_HOST", "127.0.0.1")
        serial_port = os.environ.get("MODBUS_SERIAL_PORT", "")
        allow_physical = os.environ.get("MODBUS_ALLOW_PHYSICAL_DEVICE", "").lower() == "true"
        if not allow_physical and (mode == "rtu" or not _loopback(host)):
            raise ConnectorError(
                "NOT_AUTHORIZED",
                "Physical Modbus requires explicit MODBUS_ALLOW_PHYSICAL_DEVICE=true after site approval",
            )
        self.client = ModbusReadOnlyClient(
            mode=mode, host=host, port=int(os.environ.get("MODBUS_PORT", "15020")),
            unit=int(os.environ.get("MODBUS_UNIT_ID", "1")), serial_port=serial_port,
            baudrate=int(os.environ.get("MODBUS_BAUDRATE", "9600")),
            parity=os.environ.get("MODBUS_PARITY", "N"),
            stopbits=int(os.environ.get("MODBUS_STOPBITS", "1")),
            timeout=float(os.environ.get("MODBUS_TIMEOUT", "2")),
        )

    async def connect(self) -> dict:
        return await self.health()

    async def disconnect(self) -> None:
        return None

    async def capabilities(self) -> dict:
        return {
            "protocol": "modbus", "state": "READ_ONLY", "writeback": False,
            "historical_data": False, "subscriptions": False,
            "alarms": False, "discovery": False,
        }

    async def discover_objects(self) -> list:
        return []

    async def health(self) -> dict:
        if self.client.mode == "tcp":
            try:
                await asyncio.to_thread(self._tcp_health)
                return {"status": "ONLINE", "protocol": "modbus"}
            except OSError as exc:
                return {"status": "OFFLINE", "message": str(exc), "protocol": "modbus"}
        healthy = os.path.exists(self.client.serial_port)
        return {"status": "ONLINE" if healthy else "OFFLINE", "protocol": "modbus"}

    def _tcp_health(self) -> None:
        with socket.create_connection((self.client.host, self.client.port), timeout=self.client.timeout):
            pass

    async def read_point(self, point_id: str) -> dict:
        value = await asyncio.to_thread(self.client.read, point_id)
        # Timestamp is from the Edge; physical Modbus devices typically do not send one.
        return {
            "value": value, "quality": "UNCERTAIN",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def write_value(self, point_id: str, value: Any) -> dict:
        return {"success": False, "reason": "READ_ONLY_HARDWARE_V1"}
