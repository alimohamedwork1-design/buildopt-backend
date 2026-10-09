"""BuildOpt physical-edge contract: no writes, no silent drops, no false ACK."""
from __future__ import annotations

import importlib.util
import os
import socket
import struct
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "buildopt-edge"


def edge_python(script: str, *, env: dict | None = None) -> subprocess.CompletedProcess:
    variables = {**os.environ, **(env or {})}
    variables["PYTHONPATH"] = str(EDGE)
    return subprocess.run(
        [sys.executable, "-c", script], env=variables, cwd=str(EDGE),
        capture_output=True, text=True, timeout=20,
    )


def test_modbus_read_only_crc_and_validation():
    result = edge_python("""
from app.connectors.modbus import crc16, ModbusPoint, ModbusReadOnlyClient
assert crc16(bytes.fromhex('010300000001')) == 0x0A84
assert ModbusPoint.parse('ir:0:u16:0.1').scale == 0.1
for illegal in ('ir:-1:u16', 'hr:65535:f32be', 'coil:1:f32be', 'hr:2:bool', 'hr:0:u16:nan'):
    try: ModbusPoint.parse(illegal)
    except ValueError: pass
    else: raise AssertionError('accepted invalid point: ' + illegal)
client = ModbusReadOnlyClient()
assert not hasattr(client, 'write')
""")
    assert result.returncode == 0, result.stderr


def test_modbus_denies_unapproved_physical_site():
    result = edge_python("""
from app.connectors.modbus import ModbusConnector
from app.connectors.base import ConnectorError
try: ModbusConnector()
except ConnectorError as exc: assert exc.code == 'NOT_AUTHORIZED'
else: raise AssertionError('unapproved non-loopback target allowed')
""", env={"MODBUS_MODE": "tcp", "MODBUS_HOST": "192.0.2.35", "MODBUS_ALLOW_PHYSICAL_DEVICE": "false"})
    assert result.returncode == 0, result.stderr


def test_real_socket_modbus_read_fc04():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        violations = []

        def respond():
            try:
                conn, _ = server.accept()
                with conn:
                    header = conn.recv(7)
                    tid, proto, length, unit = struct.unpack(">HHHB", header)
                    remaining = length - 1
                    request = b""
                    while len(request) < remaining:
                        request += conn.recv(remaining - len(request))
                    if proto != 0 or unit != 1 or request[0] != 4:
                        violations.append(f"unexpected request: {request.hex()}")
                    payload = bytes([4, 2, 0, 210])
                    conn.sendall(struct.pack(">HHHB", tid, 0, len(payload) + 1, unit) + payload)
            except Exception as exc:
                violations.append(str(exc))

        thread = threading.Thread(target=respond, daemon=True)
        thread.start()
        result = edge_python("""
from app.connectors.modbus import ModbusReadOnlyClient
c = ModbusReadOnlyClient(mode='tcp', host='127.0.0.1', port=int(__import__('os').environ['TEST_MODBUS_PORT']))
assert c.read('ir:0:u16:0.1') == 21.0
""", env={"TEST_MODBUS_PORT": str(port)})
        thread.join(timeout=5)
        assert not violations, violations
        assert result.returncode == 0, result.stderr


def test_queue_overlimit_does_not_delete_unacknowledged_events(tmp_path):
    path = EDGE / "app" / "storage" / "local_queue.py"
    spec = importlib.util.spec_from_file_location("safe_edge_queue", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    queue = module.LocalQueue(str(tmp_path / "buffer.db"), max_rows=2)
    for i in range(4):
        queue.enqueue(f"event{i}", f"dedupe{i}", {"value": i})
    assert queue.depth() == 4
    assert queue.metrics()["critical_overflow"] is True
    queue.close()
    recovered = module.LocalQueue(str(tmp_path / "buffer.db"), max_rows=2)
    assert recovered.depth() == 4
    recovered.close()


def test_cloud_partial_ack_and_network_failure_not_acknowledged():
    result = edge_python("""
import asyncio
import tempfile
import httpx
from app.config import EdgeSettings
from app.telemetry.uploader import CloudUploader

params = dict(gateway_id='edge-01',tenant_id='demo',building_id='site-test',
    cloud_api_url='https://mock.example',ingest_api_key='',gateway_api_key='bo_gw_test',
    poll_interval_seconds=10,queue_db_path=tempfile.mktemp(suffix='.db'),
    connector='modbus',metasys_host='',metasys_username='',metasys_password='',
    metasys_version='v4',mapped_points_file='/tmp/no-map.json')
u = CloudUploader(EdgeSettings(**params))
class Fake:
    def __init__(self, response=None, raise_error=False, **kw):
        self.response,self.raise_error=response,raise_error
    async def __aenter__(self):return self
    async def __aexit__(self,*exc):return False
    async def post(self,*args,**kwargs):
        if self.raise_error:
            raise httpx.ConnectError('WAN disconnected',request=httpx.Request('POST',args[0]))
        return self.response
async def check():
    httpx.AsyncClient=lambda **kw: Fake(httpx.Response(200,json={'accepted':1,'duplicates':0,'rejected':1,
        'gateway_id':'edge-01','building_id':'site-test'}))
    assert not await u.upload_batch([{'event_id':'a'},{'event_id':'b'}])
    httpx.AsyncClient=lambda **kw: Fake(raise_error=True)
    assert not await u.upload_batch([{'event_id':'a'}])
    assert u.upload_failures_total==2
asyncio.run(check())
""")
    assert result.returncode == 0, result.stderr
