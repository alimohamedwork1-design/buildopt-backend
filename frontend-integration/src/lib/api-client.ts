/**
 * BuildOpt AI — FastAPI backend client
 *
 * Drop into your Lovable project at: src/lib/api-client.ts
 *
 * Env vars (Lovable → Project Settings → Environment):
 *   VITE_API_URL=https://your-app.up.railway.app
 *   VITE_DEMO_MODE=false
 */

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE !== "false";

export const isApiEnabled = (): boolean => !DEMO_MODE && Boolean(API_URL);

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!isApiEnabled()) {
    throw new Error("Backend API disabled — set VITE_API_URL and VITE_DEMO_MODE=false");
  }

  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail?.en ?? body?.detail ?? `API error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// ── Buildings ──────────────────────────────────────────────────────────────

export const getBuildings = () => request<BuildingSummary[]>("/buildings");
export const getBuilding = (id: string) => request<BuildingDetail>(`/buildings/${id}`);
export const getBuildingLive = (id: string) => request<LiveBuildingData>(`/buildings/${id}/live`);
export const getBuildingMetrics = (id: string, period = "24h") =>
  request<BuildingMetrics>(`/buildings/${id}/metrics?period=${period}`);

export const sendBuildingControl = (id: string, body: ControlCommand) =>
  request<ControlResponse>(`/buildings/${id}/control`, {
    method: "POST",
    body: JSON.stringify(body),
  });

// ── Energy ─────────────────────────────────────────────────────────────────

export const getEnergyConsumption = () => request<EnergyConsumption>("/energy/consumption");
export const getEnergyForecast = (buildingId = "burj-khalifa-01", horizonHours = 24) =>
  request<EnergyForecast>(`/energy/forecast?building_id=${buildingId}&horizon_hours=${horizonHours}`);
export const getDewaTariff = () => request<DewaTariffResponse>("/energy/dewa-tariff");
export const getEnergySavings = () => request<EnergySavings>("/energy/savings");

// ── Equipment ────────────────────────────────────────────────────────────────

export const getEquipment = (buildingId?: string) =>
  request<EquipmentSummary[]>(`/equipment${buildingId ? `?building_id=${buildingId}` : ""}`);
export const getEquipmentDetail = (id: string) => request<EquipmentDetail>(`/equipment/${id}`);
export const setEquipmentSetpoint = (id: string, setpoint: number) =>
  request(`/equipment/${id}/setpoint`, {
    method: "POST",
    body: JSON.stringify({ setpoint }),
  });

// ── Alerts ───────────────────────────────────────────────────────────────────

export const getAlerts = () => request<Alert[]>("/alerts");
export const getAlertHistory = () => request<Alert[]>("/alerts/history");
export const acknowledgeAlert = (id: string, notes?: string) =>
  request(`/alerts/${id}/acknowledge`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
export const getFddResults = () => request<FDDResult[]>("/alerts/fdd");

// ── GCC ──────────────────────────────────────────────────────────────────────

export const getPrayerTimes = () => request<PrayerTimes>("/gcc/prayer-times");
export const getRamadanMode = () => request<RamadanMode>("/gcc/ramadan-mode");
export const getSandstormAlert = () => request<SandstormAlert>("/gcc/sandstorm-alert");

// ── Health ───────────────────────────────────────────────────────────────────

export const getHealth = () => request<{ status: string; demo_mode: boolean }>("/health");

// ── Types (mirror backend schemas) ─────────────────────────────────────────

export interface BuildingSummary {
  id: string;
  name: string;
  location: string;
  floors: number;
  area_sqm: number;
  status: "online" | "offline" | "maintenance";
  energy_savings_pct: number;
  active_alerts: number;
}

export interface BuildingDetail extends BuildingSummary {
  bms_type: string;
  installed_capacity_kw: number;
  last_updated: string;
}

export interface LiveBuildingData {
  building_id: string;
  timestamp: string;
  hvac: { supply_air_temp: number; return_air_temp: number; delta_t: number; power_kw: number; cop: number };
  energy: { total_kw: number; hvac_kw: number; lighting_kw: number; other_kw: number; tariff_rate: number; cost_per_hour: number };
  environment: { temp_c: number; humidity_pct: number; co2_ppm: number; pm25: number };
  active_alerts: number;
  demo_mode: boolean;
}

export interface BuildingMetrics {
  building_id: string;
  period: string;
  metrics: { timestamp: string; value: number; metric: string }[];
}

export interface ControlCommand {
  command: string;
  target: string;
  value?: number;
}

export interface ControlResponse {
  success: boolean;
  message: { en: string; ar: string };
  building_id: string;
  command: string;
}

export interface EnergyConsumption {
  timestamp: string;
  total_kw: number;
  hvac_kw: number;
  lighting_kw: number;
  other_kw: number;
  cost_aed_per_hour: number;
  demo_mode: boolean;
}

export interface EnergyForecast {
  building_id: string;
  horizon_hours: number;
  forecast: { timestamp: string; predicted_kw: number; confidence: number }[];
  demo_mode: boolean;
}

export interface DewaTariffResponse {
  month: string;
  is_summer: boolean;
  peak: { period: string; rate_aed_per_kwh: number; consumption_kwh: number; cost_aed: number };
  off_peak: { period: string; rate_aed_per_kwh: number; consumption_kwh: number; cost_aed: number };
  demand_charge_aed: number;
  total_cost_aed: number;
  demo_mode: boolean;
}

export interface EnergySavings {
  baseline_kwh: number;
  actual_kwh: number;
  savings_kwh: number;
  savings_pct: number;
  cost_saved_aed: number;
  demo_mode: boolean;
}

export interface EquipmentSummary {
  id: string;
  name: string;
  type: string;
  building_id: string;
  status: "running" | "stopped" | "fault" | "maintenance";
  power_kw: number;
  efficiency: number;
}

export interface EquipmentDetail extends EquipmentSummary {
  setpoint: number;
  current_value: number;
  last_maintenance: string;
  fault_code?: string;
}

export interface Alert {
  id: string;
  building_id: string;
  equipment_id?: string;
  severity: "critical" | "warning" | "info";
  category: string;
  title: string;
  message: string;
  message_ar: string;
  timestamp: string;
  acknowledged: boolean;
}

export interface FDDResult {
  rule_id: string;
  category: string;
  equipment_id: string;
  severity: "critical" | "warning" | "info";
  description: string;
  description_ar: string;
  confidence: number;
  detected_at: string;
}

export interface PrayerTimes {
  date: string;
  location: string;
  times: Record<string, string>;
  hvac_adjustments: { prayer: string; action: string; value: number; duration_min: number }[];
}

export interface RamadanMode {
  active: boolean;
  hijri_date: string;
  schedule: { event: string; action: string; value: number }[];
}

export interface SandstormAlert {
  active: boolean;
  pm10: number;
  threshold: number;
  actions: string[];
  timestamp: string;
}
