"""BuildOpt deployment preflight: refuse unsafe demonstration defaults.

Does NOT inspect a running container, verify backup/restore, authenticate a
client, or certify an OT installation. Run before ANY site deployment.
"""
from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

_PLACEHOLDERS = ("change-me", "example", "password", "secret", "test-", "demo", "123456")


def inspect_settings(env: dict[str, str] | None = None) -> dict:
    env = dict(os.environ) if env is None else env
    blocks: list[str] = []
    reviews: list[str] = []
    def required(key: str, min_len: int) -> None:
        value = env.get(key, "").strip()
        if not value or len(value) < min_len or any(t in value.lower() for t in _PLACEHOLDERS):
            blocks.append(f"{key}: missing, weak, or placeholder value")
    if env.get("APP_ENV", "").strip().lower() != "production":
        blocks.append("APP_ENV must explicitly be production")
    if env.get("DEMO_MODE", "").strip().lower() != "false":
        blocks.append("DEMO_MODE must explicitly be false")
    required("SECRET_KEY", 32)
    required("INFLUX_ADMIN_PASSWORD", 16)
    required("INFLUX_TOKEN", 32)
    origins = [x.strip() for x in env.get("ALLOWED_ORIGINS", "").split(",") if x.strip()]
    if not origins or "*" in origins:
        blocks.append("ALLOWED_ORIGINS must be explicitly restricted")
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            blocks.append("ALLOWED_ORIGINS must contain valid HTTPS origins only")
            break
    if env.get("CONTROL_WRITEBACK_ENABLED", "false").lower() != "false":
        blocks.append("CONTROL_WRITEBACK_ENABLED must remain false for read-only pilots")
    if env.get("OT_NETWORK_APPROVED", "").lower() != "true":
        reviews.append("Customer OT network authorization not attested")
    if env.get("TLS_REVERSE_PROXY_VERIFIED", "").lower() != "true":
        reviews.append("End-to-end TLS and reverse-proxy rules require verification")
    if env.get("OFFSITE_BACKUP_RESTORE_VERIFIED", "").lower() != "true":
        reviews.append("Backup and restore drill not yet verified")
    if env.get("CUSTOMER_SOW_SIGNED", "").lower() != "true":
        reviews.append("Signed site SOW / permissions not yet verified")
    return {
        "configuration_safe_to_attempt": len(blocks) == 0,
        "production_site_accepted": False,  # human OT and legal signoff required
        "blockers": blocks,
        "manual_acceptance_required": reviews,
        "secrets_redacted": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="No-secret-leak deployment preflight")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()
    result = inspect_settings()
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print("Safe configuration:" if result["configuration_safe_to_attempt"] else "BLOCKED:")
        for item in result["blockers"]:
            print("- " + item)
        for item in result["manual_acceptance_required"]:
            print("REVIEW: " + item)
    raise SystemExit(0 if result["configuration_safe_to_attempt"] else 2)


if __name__ == "__main__":
    main()
