"""Maps all build-opt.site routes to API data categories."""

from typing import Dict, List, Optional

# category → list of route slugs (without leading slash)
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
        "anomaly-heatmap", "energy-genome", "chiller", "solar-pv", "demand-shield",
    ],
    "equipment": ["equipment", "integration", "commissioning", "data-health", "system-status"],
    "gcc": [
        "ramadan-prayer", "ramadan-ops", "sandstorm-weather", "dewa-hub",
        "peak-season", "arabic-executive", "arabic-dashboard", "gcc-regulatory",
    ],
    "financial": [
        "roi", "budget", "financial-modeling", "financial-consolidation",
        "predictive-budget", "tenant-billing", "vendors", "benchmarking",
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

# Build reverse lookup: slug → category
ROUTE_TO_CATEGORY: Dict[str, str] = {}
for category, slugs in MODULE_CATEGORIES.items():
    for slug in slugs:
        ROUTE_TO_CATEGORY[slug or ""] = category

# All known routes (172+ feature routes from site audit)
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

# Assign uncategorized routes to "generic"
for route in ALL_ROUTES:
    if route not in ROUTE_TO_CATEGORY:
        ROUTE_TO_CATEGORY[route] = "generic"

GENERIC_CATEGORY = "generic"


def get_category(route: str) -> str:
    slug = route.strip("/").split("/")[0] if route else ""
    return ROUTE_TO_CATEGORY.get(slug, GENERIC_CATEGORY)


def list_modules() -> List[Dict[str, str]]:
    modules = []
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
        })
    return modules
