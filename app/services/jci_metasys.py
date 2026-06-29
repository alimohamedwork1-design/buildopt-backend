from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.services import demo_mode


class JCIMetasysClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        version: str = "v4",
        demo_mode: bool = True,
    ) -> None:
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.version = version
        self.demo_mode = demo_mode
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def health_probe(self) -> Dict[str, Any]:
        """Live ping — login + object count for protocol health."""
        if self.demo_mode or not self.host:
            return {"status": "not_configured", "response_ms": 0, "object_count": 0}

        start = time.perf_counter()
        token = await self._ensure_token()
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        if not token:
            return {"status": "disconnected", "response_ms": elapsed_ms, "object_count": 0}

        try:
            objects = await self.get_objects()
            return {
                "status": "connected",
                "response_ms": elapsed_ms,
                "object_count": len(objects),
            }
        except Exception:
            return {"status": "disconnected", "response_ms": elapsed_ms, "object_count": 0}

    def status(self) -> str:
        if self.demo_mode:
            return "simulated"
        if not self.host:
            return "not_configured"
        return "ready"

    async def _ensure_token(self) -> Optional[str]:
        if self.demo_mode:
            return "demo-token"

        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        if not self.host:
            return None

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{self.host}/api/{self.version}/login",
                json={"username": self.username, "password": self.password},
            )
            if response.status_code != 200:
                return None

            data = response.json()
            self._token = data.get("accessToken") or data.get("token")
            self._token_expiry = now + timedelta(minutes=14)
            return self._token

    async def _auth_headers(self) -> Dict[str, str]:
        token = await self._ensure_token()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    async def get_objects(self) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return demo_mode.get_jci_objects()

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.host}/api/{self.version}/objects", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_present_value(self, object_id: str) -> Any:
        if self.demo_mode:
            for obj in demo_mode.get_jci_objects():
                if obj["id"] == object_id:
                    return obj.get("present_value")
            return None

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.host}/api/{self.version}/objects/{object_id}/attributes/presentValue",
                headers=headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def write_command(self, object_id: str, attribute: str, value: Any) -> bool:
        if self.demo_mode:
            return True

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.patch(
                f"{self.host}/api/{self.version}/objects/{object_id}",
                headers=headers,
                json={"attributes": {attribute: value}},
            )
            return response.status_code in (200, 204)

    async def get_alarms(self) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return demo_mode.get_jci_alarms()

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.host}/api/{self.version}/alarms", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_trend(self, object_id: str) -> List[Dict[str, Any]]:
        if self.demo_mode:
            return demo_mode.get_jci_trend(object_id)

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.host}/api/{self.version}/trends/{object_id}/trendedAttributes",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(
        self,
        host: str,
        username: str,
        password: str,
        version: str = "v4",
    ) -> Dict[str, Any]:
        if self.demo_mode:
            return {
                "status": "connected",
                "message": f"Metasys {version} connected successfully",
                "response_ms": 145,
                "server_version": version,
                "ssl_valid": True,
                "demo": True,
            }

        host = host.rstrip("/")
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{host}/api/{version}/login",
                    json={"username": username, "password": password},
                )
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if response.status_code == 200:
                ssl_valid = self._check_ssl_valid(host)
                return {
                    "status": "connected",
                    "message": f"Metasys {version} connected successfully",
                    "response_ms": elapsed_ms,
                    "server_version": version,
                    "ssl_valid": ssl_valid,
                }
            return self._connection_failure("Invalid credentials", "بيانات خاطئة")
        except httpx.TimeoutException:
            return self._connection_failure("Timeout", "انتهى الوقت")
        except httpx.ConnectError:
            return self._connection_failure("Connection refused", "فشل الاتصال")
        except Exception as exc:
            return self._connection_failure(str(exc), "فشل الاتصال")

    async def network_diagnostic(
        self,
        host: str,
        username: str,
        password: str,
        version: str = "v4",
    ) -> Dict[str, Any]:
        if self.demo_mode:
            return {
                "checks": [
                    {"step": "DNS Resolution", "status": "pass", "detail": "Resolved in 45ms"},
                    {"step": "TCP Port 443", "status": "pass", "detail": "Port open"},
                    {"step": "SSL Certificate", "status": "pass", "detail": "Valid until 2025-12-01"},
                    {"step": "Metasys API Response", "status": "pass", "detail": "v4 responded in 312ms"},
                    {"step": "JWT Login", "status": "pass", "detail": "Token obtained successfully"},
                    {"step": "Token Refresh", "status": "pass", "detail": "14 min refresh interval configured"},
                ],
                "overall": "pass",
                "summary": "All checks passed. Metasys is ready for live data.",
                "summary_ar": "جميع الفحوصات نجحت. Metasys جاهز للبيانات الحية.",
                "demo": True,
            }

        host = host.rstrip("/")
        parsed = urlparse(host if "://" in host else f"https://{host}")
        hostname = parsed.hostname or host
        port = parsed.port or (443 if parsed.scheme != "http" else 80)
        checks: List[Dict[str, str]] = []

        dns_start = time.perf_counter()
        try:
            socket.getaddrinfo(hostname, port)
            dns_ms = int((time.perf_counter() - dns_start) * 1000)
            checks.append({"step": "DNS Resolution", "status": "pass", "detail": f"Resolved in {dns_ms}ms"})
        except socket.gaierror:
            checks.append({"step": "DNS Resolution", "status": "fail", "detail": "Could not resolve host"})
            return self._diagnostic_result(checks, False)

        try:
            sock = socket.create_connection((hostname, port), timeout=10)
            sock.close()
            checks.append({"step": f"TCP Port {port}", "status": "pass", "detail": "Port open"})
        except OSError:
            checks.append({"step": f"TCP Port {port}", "status": "fail", "detail": "Port closed or unreachable"})
            return self._diagnostic_result(checks, False)

        ssl_detail = self._ssl_detail(hostname, port)
        ssl_ok = ssl_detail.startswith("Valid")
        checks.append(
            {
                "step": "SSL Certificate",
                "status": "pass" if ssl_ok else "fail",
                "detail": ssl_detail,
            }
        )
        if not ssl_ok and port == 443:
            return self._diagnostic_result(checks, False)

        api_start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{host}/api/{version}/login",
                    json={"username": username, "password": password},
                )
            api_ms = int((time.perf_counter() - api_start) * 1000)
            if response.status_code != 200:
                checks.append(
                    {
                        "step": "Metasys API Response",
                        "status": "fail",
                        "detail": f"HTTP {response.status_code}",
                    }
                )
                checks.append({"step": "JWT Login", "status": "fail", "detail": "Authentication failed"})
                return self._diagnostic_result(checks, False)

            checks.append(
                {
                    "step": "Metasys API Response",
                    "status": "pass",
                    "detail": f"{version} responded in {api_ms}ms",
                }
            )
            checks.append({"step": "JWT Login", "status": "pass", "detail": "Token obtained successfully"})
            checks.append(
                {
                    "step": "Token Refresh",
                    "status": "pass",
                    "detail": "14 min refresh interval configured",
                }
            )
            return self._diagnostic_result(checks, True)
        except httpx.TimeoutException:
            checks.append({"step": "Metasys API Response", "status": "fail", "detail": "Request timed out"})
            return self._diagnostic_result(checks, False)
        except Exception as exc:
            checks.append({"step": "Metasys API Response", "status": "fail", "detail": str(exc)})
            return self._diagnostic_result(checks, False)

    @staticmethod
    def _connection_failure(error: str, error_ar: str) -> Dict[str, Any]:
        return {"status": "failed", "error": error, "error_ar": error_ar}

    @staticmethod
    def _diagnostic_result(checks: List[Dict[str, str]], passed: bool) -> Dict[str, Any]:
        if passed:
            return {
                "checks": checks,
                "overall": "pass",
                "summary": "All checks passed. Metasys is ready for live data.",
                "summary_ar": "جميع الفحوصات نجحت. Metasys جاهز للبيانات الحية.",
            }
        return {
            "checks": checks,
            "overall": "fail",
            "summary": "One or more checks failed. Review details before enabling live data.",
            "summary_ar": "فشلت واحدة أو أكثر من الفحوصات. راجع التفاصيل قبل تفعيل البيانات الحية.",
        }

    @staticmethod
    def _check_ssl_valid(host: str) -> bool:
        parsed = urlparse(host if "://" in host else f"https://{host}")
        hostname = parsed.hostname or host
        port = parsed.port or 443
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname):
                    return True
        except Exception:
            return False

    @staticmethod
    def _ssl_detail(hostname: str, port: int) -> str:
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_after = cert.get("notAfter", "")
                    if not_after:
                        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        return f"Valid until {expiry.date().isoformat()}"
                    return "Valid certificate"
        except Exception as exc:
            return f"Invalid: {exc}"
