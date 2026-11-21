"""Manufacturer-independent protocol readiness and evidence gating.

Readiness means *ready for a controlled assessment*, not field certification.
No data acquisition, control writes, credentials, or source identifiers are
accepted by these pure functions.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Protocol(str, Enum):
    BACNET_IP = "bacnet_ip"
    MODBUS_TCP = "modbus_tcp"
    MQTT = "mqtt"
    OPC_UA = "opc_ua"
    REST = "rest"
    HISTORIAN = "historian"


# Code existence only, not a promise of compatibility or site testing.
_IMPLEMENTATIONS: dict[Protocol, str] = {
    Protocol.BACNET_IP: "backend_adapter_code_present",
    Protocol.MODBUS_TCP: "backend_adapter_code_present",
    Protocol.MQTT: "backend_adapter_code_present",
    Protocol.OPC_UA: "site_adapter_required",
    Protocol.REST: "site_adapter_required",
    Protocol.HISTORIAN: "import_mapping_required",
}

_REQUIREMENTS = (
    "owner_access_authorized",
    "network_access_approved",
    "read_only_scope_confirmed",
    "sample_data_observed",
    "timestamp_and_units_verified",
    "point_mapping_accepted",
    "disconnection_recovery_tested",
)


class SiteAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    building_id: str = Field(min_length=1, max_length=160)
    protocol: Protocol
    owner_access_authorized: bool = False
    network_access_approved: bool = False
    read_only_scope_confirmed: bool = False
    sample_data_observed: bool = False
    timestamp_and_units_verified: bool = False
    point_mapping_accepted: bool = False
    disconnection_recovery_tested: bool = False
    # An attestation via API never substitutes for signed site acceptance.
    engineer_signoff_recorded: bool = False
    writeback_requested: Literal[False] = False


def get_compatibility_matrix() -> list[dict]:
    return [
        {
            "protocol": protocol.value,
            "implementation_status": implementation,
            "lab_validation": "not_verified",
            "field_validation": "not_verified",
            "site_assessment_required": True,
            "writeback": "disabled",
        }
        for protocol, implementation in _IMPLEMENTATIONS.items()
    ]


def assess_site(payload: SiteAssessment) -> dict:
    checklist = {key: getattr(payload, key) for key in _REQUIREMENTS}
    unmet = [key for key, value in checklist.items() if not value]
    if not payload.owner_access_authorized:
        status = "owner_authorization_required"
    elif not payload.network_access_approved or not payload.read_only_scope_confirmed:
        status = "security_scope_required"
    elif unmet:
        status = "engineering_review_required"
    else:
        status = "ready_for_evidence_review"
    return {
        "building_id": payload.building_id,
        "protocol": payload.protocol.value,
        "status": status,
        "implementation_status": _IMPLEMENTATIONS[payload.protocol],
        "checks": checklist,
        "unmet_requirements": unmet,
        "engineer_signoff_recorded": payload.engineer_signoff_recorded,
        "field_validation": "not_certified",
        "auto_connect_attempted": False,
        "writeback": "disabled",
        "scope_note": (
            "This is a self-reported checklist only. A separately approved "
            "field test and signed evidence are mandatory for certification."
        ),
    }


class TwinReadinessRequest(BaseModel):
    """Read-only digital-twin readiness — neither a simulation nor a twin model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    building_id: str = Field(min_length=1, max_length=160)
    declared_assets: int = Field(ge=0, le=100_000)
    approved_asset_mappings: int = Field(ge=0, le=100_000)
    point_history_verified: bool = False
    units_and_clock_verified: bool = False
    baseline_method_approved: bool = False
    read_only: Literal[True] = True


def twin_readiness(request: TwinReadinessRequest) -> dict:
    if request.approved_asset_mappings > request.declared_assets:
        raise ValueError("Approved mapping count exceeds declared assets")
    checks = {
        "assets_declared": request.declared_assets > 0,
        "all_assets_mapped": (
            request.declared_assets > 0
            and request.approved_asset_mappings == request.declared_assets
        ),
        "point_history_verified": request.point_history_verified,
        "units_and_clock_verified": request.units_and_clock_verified,
        "baseline_method_approved": request.baseline_method_approved,
    }
    return {
        "building_id": request.building_id,
        "status": "ready_for_model_validation" if all(checks.values()) else "insufficient_evidence",
        "checks": checks,
        "missing": [name for name, accepted in checks.items() if not accepted],
        "model_validated": False,
        "real_savings_verified": False,
        "automatic_control_enabled": False,
        "note": "A readiness response is not a calibrated digital twin, verified savings, or permission to control equipment.",
    }
