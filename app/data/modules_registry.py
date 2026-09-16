"""BuildOpt module registry and product-truth capability metadata.

The registry intentionally separates route availability from implementation maturity.
A page existing in the product does not imply that its domain engine is production-ready.
"""

from typing import Any, Dict, List, Literal

ModuleMaturity = Literal["production", "pilot", "heuristic", "simulated", "concept"]

MODULE_CATEGORIES: Dict[str, List[str]] = {
    "overview": [""],
    "telemetry": ["telemetry"],
    "portfolio": ["portfolio", "executive", "client-portfolio"],
    "alerts": ["alerts"],
    "work_orders": ["work-orders", "conversational-wo", "shift-handover"],
    "reports": ["reports", "executive-briefing"],
    "ai_chat": ["ai-chat", "ai-explainer", "ai-recommendations", "causal-chain", "causal-ai"],
    "fault_prediction": ["fault-prediction", "fdd", "anomaly-explainer", "anomaly-heatmap"],
    "optimization": ["optimization", "autopilot", "whatif", "digital-twin", "demand-response", "occupancy"],
    "energy": [
        "utility-rate", "tariff-intelligence", "dewa-hub", "metering-reconciliation",
        "anomaly-heatmap", "energy-genome", "chiller", "industrial-refrigeration", "solar-pv", "demand-shield",
    ],
    "financial": [
        "roi", "budget", "financial-modeling", "financial-consolidation", "predictive-budget",
        "tenant-billing", "vendors", "benchmarking",
    ],
    "equipment": ["equipment", "integration", "commissioning", "data-health", "system-status"],
    "gcc": [
        "ramadan-prayer", "ramadan-ops", "sandstorm-weather", "dewa-hub", "peak-season",
        "arabic-executive", "arabic-dashboard", "gcc-regulatory",
    ],
    "carbon": ["carbon", "scope3", "lifecycle-carbon", "supply-chain-carbon", "net-zero", "sustainability-roadmap"],
    "tenant": ["tenant", "tenant-portal", "tenant-experience", "building-experience", "occupant-feedback"],
    "security": ["security-access", "cyber-security", "incident-command", "access-control"],
    "jci": [
        "openblue-bridge", "metasys-deep-link", "jci-migration", "tag-mapper",
        "migration-simulator", "setpoint-writeback",
    ],
    "investor": ["investor", "investor-report", "valuation-impact", "exit-readiness", "how-it-works", "journey"],
    "compliance": ["compliance", "regulatory-monitor", "eu-compliance", "us-compliance", "leed-scorer"],
    "wellness": ["wellness", "wellness-os", "iaq", "air-quality-index", "thermal-comfort", "health-certificate"],
    "infrastructure": ["water", "vertical-transport", "backup-power", "sensor-mesh", "bim-integration"],
}

ROUTE_TO_CATEGORY: Dict[str, str] = {}
for category, slugs in MODULE_CATEGORIES.items():
    for slug in slugs:
        ROUTE_TO_CATEGORY[slug or ""] = category

ALL_ROUTES: List[str] = sorted(set(
    [s for slugs in MODULE_CATEGORIES.values() for s in slugs if s]
    + [
        "adaptive-setpoints", "agentic-ai", "ai-agents", "ai-audit-trail", "ai-governance",
        "air-quality-trading", "api-marketplace", "ar-field-ops", "asset-registry",
        "autonomous-control", "autonomous-learning", "battery-storage", "biodiversity",
        "building-passport", "carbon-aware-compute", "carbon-marketplace", "carbon-trading",
        "carbon-vault", "circular-economy", "climate-risk", "comfort-ai", "commissioning-assistant",
        "construction-handover", "contractor-performance", "data-normalization", "data-sovereignty",
        "digital-loto", "digital-noc", "district-energy", "drone-fleet", "ecosystem", "edge-fleet",
        "emergency-response", "ev-fleet", "federated-learning", "generative-retrofit",
        "green-finance", "green-lease", "grid-interactivity", "grid-services", "handover",
        "human-twin", "insurance-risk", "insurance-vault", "load-balancing", "maintenance-contracts",
        "material-passport", "microclimate", "night-mode", "occupant-experience", "physics-twin",
        "portfolio-benchmarking", "power-quality", "predictive", "predictive-insurance",
        "procurement", "protocol-translator", "quantum-optimizer", "retrofit-planner", "retrofit-roi",
        "self-healing", "smart-district", "sovereign-llm", "space-optimizer", "space-utilization",
        "spare-parts", "supply-chain", "tag-mapper", "tender-assistant", "tenant-carbon-market",
        "lease-intelligence", "twin-simulation", "voice-twin", "white-label", "settings",
    ]
))

for route in ALL_ROUTES:
    if route not in ROUTE_TO_CATEGORY:
        ROUTE_TO_CATEGORY[route] = "generic"

GENERIC_CATEGORY = "generic"

PRODUCTION_MODULES = frozenset({
    "telemetry",
    "data-health",
    "equipment",
    "alerts",
    "fdd",
    "system-status",
})

PILOT_MODULES = frozenset({
    "overview",
    "portfolio",
    "reports",
    "ai-chat",
    "ai-recommendations",
    "industrial-refrigeration",
    "integration",
    "commissioning",
    "roi",
    "openblue-bridge",
    "metasys-deep-link",
    "tag-mapper",
    "setpoint-writeback",
    "settings",
})

HEURISTIC_MODULES = frozenset({
    "optimization",
    "autopilot",
    "whatif",
    "digital-twin",
    "demand-response",
    "adaptive-setpoints",
    "load-balancing",
    "chiller",
    "fault-prediction",
    "anomaly-explainer",
    "anomaly-heatmap",
    "predictive",
    "causal-chain",
    "causal-ai",
    "commissioning-assistant",
})

CONCEPT_MODULES = frozenset({
    "quantum-optimizer",
    "drone-fleet",
    "sovereign-llm",
    "voice-twin",
    "human-twin",
    "air-quality-trading",
    "tenant-carbon-market",
    "carbon-vault",
    "self-healing",
    "federated-learning",
    "generative-retrofit",
    "biodiversity",
    "carbon-aware-compute",
})

CORE_PILOT_MODULES = frozenset({
    "overview",
    "portfolio",
    "telemetry",
    "data-health",
    "equipment",
    "fdd",
    "alerts",
    "ai-chat",
    "ai-recommendations",
    "optimization",
    "reports",
    "integration",
    "system-status",
    "settings",
})


def get_category(route: str) -> str:
    slug = route.strip("/").split("/")[0] if route else ""
    return ROUTE_TO_CATEGORY.get(slug, GENERIC_CATEGORY)


def get_module_capability(route: str) -> Dict[str, Any]:
    slug = (route or "overview").strip("/").split("/")[0] or "overview"
    if slug in PRODUCTION_MODULES:
        maturity: ModuleMaturity = "production"
        engine_mode = "specialized_live"
        truth = "Dedicated live backend path exists; site validation still applies."
    elif slug in PILOT_MODULES:
        maturity = "pilot"
        engine_mode = "specialized_pilot"
        if slug == "ai-chat":
            truth = "Evidence/tool assistant over live BuildOpt services; not a standalone calibrated LLM."
        elif slug == "portfolio":
            truth = "Uses the real building registry; portfolio KPIs are shown only when source fields exist."
        else:
            truth = "Real services/data are composed, but site-specific pilot validation is required."
    elif slug in HEURISTIC_MODULES:
        maturity = "heuristic"
        engine_mode = "rule_or_derived"
        truth = "Uses rules or derived calculations; not a validated trained ML engine."
    elif slug in CONCEPT_MODULES:
        maturity = "concept"
        engine_mode = "concept_only"
        truth = "Product concept surface; no production live engine is claimed."
    else:
        maturity = "simulated"
        engine_mode = "generic_demo_or_live_shell"
        truth = "UI/data shell exists; domain-specific production engine is not yet implemented."

    return {
        "maturity": maturity,
        "engine_mode": engine_mode,
        "core_pilot": slug in CORE_PILOT_MODULES,
        "truth": truth,
    }


def list_modules() -> List[Dict[str, Any]]:
    modules: List[Dict[str, Any]] = []
    seen = set()
    for route in [""] + ALL_ROUTES:
        slug = route or "overview"
        if slug in seen:
            continue
        seen.add(slug)
        cat = get_category(route)
        modules.append({
            "slug": slug,
            "path": f"/{route}" if route else "/",
            "category": cat,
            "api_endpoint": f"/api/v1/modules/{slug}/data",
            **get_module_capability(slug),
        })
    return modules
