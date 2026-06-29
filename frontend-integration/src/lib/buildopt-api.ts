/**
 * BuildOpt AI — Complete backend client for all 172+ modules
 * Drop into: src/lib/buildopt-api.ts
 *
 * Requires .env:
 *   VITE_API_URL=https://buildopt-backend-production.up.railway.app
 *   VITE_DEMO_MODE=false
 */

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "false";
const DEFAULT_BUILDING = "burj-khalifa-01";

export const isApiEnabled = (): boolean => !DEMO_MODE && Boolean(API_URL);
export const getApiUrl = (): string => API_URL;
export const getDefaultBuildingId = (): string => DEFAULT_BUILDING;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!isApiEnabled()) throw new Error("API disabled — set VITE_API_URL and VITE_DEMO_MODE=false");
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(init?.headers ?? {}) },
    signal: init?.signal ?? AbortSignal.timeout(12000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail?.en ?? body?.detail ?? `API ${response.status}`);
  }
  return response.json() as Promise<T>;
}

// ── Site ─────────────────────────────────────────────────────────────────────
export const getSiteMetadata = () => request<SiteMetadata>("/site/metadata");
export const getSiteConfig = () => request<SiteConfig>("/site/config");

// ── Modules (all 172 pages) ──────────────────────────────────────────────────
export const listModules = () => request<ModuleListItem[]>("/modules");
export const getModuleData = (slug: string, buildingId = DEFAULT_BUILDING) =>
  request<ModuleDataPayload>(`/modules/${slug}/data?building_id=${buildingId}`);

// ── Sessions (login tracking) ────────────────────────────────────────────────
export const trackSessionEvent = (event: SessionEventPayload) =>
  request<{ success: boolean; event_id: string }>("/sessions/events", {
    method: "POST",
    body: JSON.stringify(event),
  });
export const getSessionStats = () => request<SessionStats>("/sessions/stats");

// ── Buildings ────────────────────────────────────────────────────────────────
export const getBuildings = () => request<BuildingSummary[]>("/buildings");
export const getBuildingLive = (id = DEFAULT_BUILDING) => request<LiveBuildingData>(`/buildings/${id}/live`);
export const getBuildingMetrics = (id = DEFAULT_BUILDING, period = "24h") =>
  request<BuildingMetrics>(`/buildings/${id}/metrics?period=${period}`);

// ── Energy ───────────────────────────────────────────────────────────────────
export const getEnergyConsumption = (buildingId = DEFAULT_BUILDING) =>
  request<EnergyConsumption>(`/energy/consumption?building_id=${buildingId}`);
export const getEnergyForecast = (buildingId = DEFAULT_BUILDING, hours = 24) =>
  request<EnergyForecast>(`/energy/forecast?building_id=${buildingId}&horizon_hours=${hours}`);
export const getDewaTariff = () => request<DewaTariffResponse>("/energy/dewa-tariff");
export const getEnergySavings = () => request<EnergySavings>("/energy/savings");

// ── Equipment ────────────────────────────────────────────────────────────────
export const getEquipment = (buildingId?: string) =>
  request<EquipmentSummary[]>(`/equipment${buildingId ? `?building_id=${buildingId}` : ""}`);

// ── Alerts & FDD ─────────────────────────────────────────────────────────────
export const getAlerts = () => request<Alert[]>("/alerts");
export const getFddResults = () => request<FDDResult[]>("/alerts/fdd");
export const acknowledgeAlert = (id: string, notes?: string) =>
  request(`/alerts/${id}/acknowledge`, { method: "POST", body: JSON.stringify({ notes }) });

// ── GCC ──────────────────────────────────────────────────────────────────────
export const getPrayerTimes = () => request<PrayerTimes>("/gcc/prayer-times");
export const getRamadanMode = () => request<RamadanMode>("/gcc/ramadan-mode");
export const getSandstormAlert = () => request<SandstormAlert>("/gcc/sandstorm-alert");

// ── Health ───────────────────────────────────────────────────────────────────
export const getHealth = () => request<HealthResponse>("/health");
export const getConnections = () => request<ConnectionsResponse>("/health/connections");
export const getProtocolHealth = () => request<ProtocolHealthResponse>("/health/protocols");
export const getHealthHistory = (hours = 24) => request<HealthHistoryResponse>(`/health/history?hours=${hours}`);
export const getHealthLogs = (limit = 10) => request<HealthLogsResponse>(`/health/logs?limit=${limit}`);
export const getHealthPipeline = () => request<HealthPipelineResponse>("/health/pipeline");
export const testAlertWebhook = () => request<WebhookTestResponse>("/health/alert-webhook/test", { method: "POST" });

// ── JCI Metasys ──────────────────────────────────────────────────────────────
export const testJciConnection = (body: JciConnectionRequest) =>
  request<JciConnectionResult>("/jci/test-connection", { method: "POST", body: JSON.stringify(body) });
export const saveJciCredentials = (body: JciConnectionRequest) =>
  request<JciSaveResult>("/jci/save-credentials", { method: "POST", body: JSON.stringify(body) });
export const runJciNetworkDiagnostic = (body: JciConnectionRequest) =>
  request<JciDiagnosticResult>("/jci/network-diagnostic", { method: "POST", body: JSON.stringify(body) });

/** @deprecated use getProtocolHealth — V2 returns full protocol array */
export const getProtocolStatus = () => getProtocolHealth();

// ── Types ────────────────────────────────────────────────────────────────────
export interface SiteMetadata {
  name: string; version: string; frontend_url: string; api_url: string;
  building_default: string; building_name: string; timezone: string;
  demo_mode: boolean; modules_count: number;
}
export interface SiteConfig {
  default_building_id: string; poll_intervals_ms: Record<string, number>; session_events_enabled: boolean;
}
export interface ModuleListItem { slug: string; path: string; category: string; api_endpoint: string }
export interface ModuleDataPayload {
  slug: string; path: string; category: string; building_id: string; timestamp: string;
  metric_cards: { label: string; unit: string; value: number; trend_pct: number }[];
  live?: LiveBuildingData; energy?: EnergyConsumption; savings?: EnergySavings;
  forecast?: EnergyForecast; alerts?: Alert[]; fdd?: FDDResult[]; equipment?: EquipmentSummary[];
  dewa_tariff?: DewaTariffResponse; recommendations: { priority: string; title: string; savings_aed_per_month: number }[];
  recent_activity: { message: string; minutes_ago: number }[];
  charts: Record<string, unknown>; demo_mode: boolean;
}
export interface SessionEventPayload {
  event_type: "login" | "logout" | "page_view" | "module_open" | "signup" | "password_reset";
  user_id?: string; email?: string; role?: string; module_path?: string;
  metadata?: Record<string, unknown>;
}
export interface SessionStats { total_events: number; total_logins: number; unique_users: number; last_login: string | null }
export interface LiveBuildingData {
  building_id: string; timestamp: string;
  hvac: { supply_air_temp: number; return_air_temp: number; delta_t: number; power_kw: number; cop: number };
  energy: { total_kw: number; hvac_kw: number; lighting_kw: number; other_kw: number; tariff_rate: number; cost_per_hour: number };
  environment: { temp_c: number; humidity_pct: number; co2_ppm: number; pm25: number };
  active_alerts: number; demo_mode: boolean;
}
export interface BuildingSummary {
  id: string; name: string; location: string; floors: number; area_sqm: number;
  status: string; energy_savings_pct: number; active_alerts: number;
}
export interface BuildingMetrics { building_id: string; period: string; metrics: { timestamp: string; value: number; metric: string }[] }
export interface EnergyConsumption {
  timestamp: string; total_kw: number; hvac_kw: number; lighting_kw: number;
  other_kw: number; cost_aed_per_hour: number; demo_mode: boolean;
}
export interface EnergyForecast {
  building_id: string; horizon_hours: number;
  forecast: { timestamp: string; predicted_kw: number; confidence: number }[]; demo_mode: boolean;
}
export interface DewaTariffResponse {
  month: string; is_summer: boolean; total_cost_aed: number;
  peak: { rate_aed_per_kwh: number; consumption_kwh: number; cost_aed: number };
  off_peak: { rate_aed_per_kwh: number; consumption_kwh: number; cost_aed: number };
}
export interface EnergySavings { savings_pct: number; savings_kwh: number; cost_saved_aed: number; demo_mode: boolean }
export interface EquipmentSummary { id: string; name: string; type: string; status: string; power_kw: number; efficiency: number }
export interface Alert {
  id: string; severity: string; category: string; title: string; message: string;
  message_ar: string; timestamp: string; acknowledged: boolean;
}
export interface FDDResult { rule_id: string; category: string; description: string; severity: string; confidence: number }
export interface PrayerTimes { date: string; location: string; times: Record<string, string> }
export interface RamadanMode { active: boolean; hijri_date: string; schedule: unknown[] }
export interface SandstormAlert { active: boolean; pm10: number; threshold: number; actions: string[] }
export interface HealthResponse {
  status: string; version: string; demo_mode: boolean; timestamp: string;
  health_score?: number; health_label?: string; health_label_ar?: string; uptime_seconds?: number;
}
export interface ConnectionsResponse {
  demo_mode: boolean; influxdb: string; supabase: string; jci_metasys?: string;
  alert_webhook: boolean; ingest_api: boolean; frontend?: string; api_url?: string;
}
export interface ProtocolHealthItem {
  name: string; status: string; last_seen: string | null; last_seen_human?: string | null;
  data_points?: number; response_ms?: number; write_rate?: string; alerts_count?: number;
}
export interface ProtocolHealthResponse {
  protocols: ProtocolHealthItem[]; overall_health: string; timestamp: string;
}
export interface HealthHistoryResponse {
  interval_minutes: number; demo_mode?: boolean;
  data: { timestamp: string; response_ms: number; status: string }[];
}
export interface HealthLogsResponse {
  logs: { timestamp: string; level: string; message: string; message_ar?: string }[];
}
export interface HealthPipelineResponse {
  jobs: {
    name: string; name_ar: string; interval: string; status: string;
    last_run: string; last_run_human: string; next_run_human: string;
  }[];
}
export interface WebhookTestResponse {
  status: string; webhook_url?: string; http_status?: number; message?: string; demo_mode?: boolean;
}
export interface JciConnectionRequest { host: string; username: string; password: string; version?: string }
export interface JciConnectionResult {
  status: string; message?: string; response_ms?: number; server_version?: string;
  ssl_valid?: boolean; demo?: boolean; error?: string; error_ar?: string;
}
export interface JciSaveResult { status: string; message: string; message_ar: string; supabase_persisted?: boolean }
export interface JciDiagnosticResult {
  checks: { step: string; status: string; detail: string }[];
  overall: string; summary: string; summary_ar: string; demo?: boolean;
}
/** @deprecated V1 shape — use ProtocolHealthResponse */
export interface ProtocolStatus { bacnet: string; modbus: string; mqtt: string; jci_metasys: string }
