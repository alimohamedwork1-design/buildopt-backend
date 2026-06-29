/**
 * SYNCED FROM buildopt-ai/src/lib/api-client.ts — do not edit here; copy from frontend on release.
 * BuildOpt AI — FastAPI Backend Client
 * Wires the frontend to the external FastAPI service.
 * Env: VITE_API_URL + VITE_DEMO_MODE.
 * isApiEnabled() respects localStorage override "buildopt_demo_mode".
 */

const env = (import.meta as any).env || {};
export const API_URL: string = env.VITE_API_URL || env.API_URL || '';
const ENV_DEMO_MODE: string = String(env.VITE_DEMO_MODE ?? env.DEMO_MODE ?? 'true').toLowerCase();

export function isApiEnabled(): boolean {
  try {
    const override = typeof window !== 'undefined' ? window.localStorage.getItem('buildopt_demo_mode') : null;
    if (override === 'true') return false; // force demo
    if (override === 'false') return !!API_URL; // force live
  } catch {}
  return ENV_DEMO_MODE === 'false' && !!API_URL;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: init?.method ?? 'GET',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...(init?.headers || {}) },
    body: init?.body,
    signal: init?.signal ?? AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`API ${res.status} ${res.statusText} @ ${path}`);
  return res.json() as Promise<T>;
}

const get = <T,>(p: string) => request<T>(p);
const post = <T,>(p: string, body: any) => request<T>(p, { method: 'POST', body: JSON.stringify(body) });

// ---------- Types ----------
export interface Building { id: string; name: string; city?: string; area_m2?: number; occupancy?: number; }
export interface LiveBuildingData {
  building_id: string; timestamp: string;
  hvac: { power_kw: number; cop: number; chiller_kw?: number; supply_temp_c?: number; return_temp_c?: number; fan_speed_pct?: number; };
  energy: { total_kw: number; peak_kw?: number; today_kwh?: number; cost_today_aed?: number; };
  environment: { indoor_temp_c: number; indoor_rh?: number; co2_ppm: number; outdoor_temp_c?: number; outdoor_rh?: number; };
}
export interface EnergyConsumptionPoint { timestamp: string; kwh: number; cost_aed?: number; }
export interface EnergyForecastPoint { timestamp: string; kwh: number; confidence?: number; }
export interface DewaTariff { peak_rate: number; off_peak_rate: number; shoulder_rate: number; peak_hours?: string; off_peak_hours?: string; shoulder_hours?: string; demand_charge_rate?: number; power_factor_threshold?: number; }
export interface EnergySavings { saved_kwh: number; saved_aed: number; baseline_kwh: number; }
export interface Equipment { id: string; name: string; type: string; status: string; health: number; supply_temp_c?: number; fan_speed_pct?: number; }
export interface AlertItem { id: string; title: string; severity: string; status: string; source?: string; module?: string; message?: string; message_ar?: string; created_at: string; }
export interface FddResult { id: string; rule: string; severity: string; equipment_id?: string; description: string; cost_per_day?: number; detected_at: string; }
export interface PrayerTimes { date: string; fajr: string; dhuhr: string; asr: string; maghrib: string; isha: string; }
export interface RamadanMode { active: boolean; iftar_time?: string; suhoor_time?: string; schedule_shift_min?: number; }
export interface SandstormAlert { active: boolean; severity?: string; eta?: string; pm10?: number; pm25?: number; }
export interface ApiHealth { status: string; version?: string; uptime_s?: number; response_ms?: number; health_score?: number; }
export interface SiteMetadata { building_name?: string; version?: string; environment?: string; deployed_at?: string; }
export interface ProtocolConnection { name: string; status: string; last_seen?: string; data_points?: number; response_ms?: number; }
export interface ConnectionsResponse { ingest_api?: ProtocolConnection; alert_webhook?: ProtocolConnection; metasys?: ProtocolConnection; influxdb?: ProtocolConnection; supabase?: ProtocolConnection; bacnet?: ProtocolConnection; modbus?: ProtocolConnection; [k: string]: ProtocolConnection | undefined; }
export interface ModuleData {
  slug: string;
  metric_cards?: Array<{ label: string; value: string | number; unit?: string; accent?: string; trend?: number; trend_pct?: number }>;
  recommendations?: Array<{ id: string; title: string; impact?: string; priority?: string }>;
  recent_activity?: Array<{ id: string; timestamp: string; type: string; message: string }>;
  charts?: Record<string, any>;
  live?: { hvac?: LiveBuildingData['hvac']; energy?: LiveBuildingData['energy']; environment?: LiveBuildingData['environment'] };
  alerts?: AlertItem[];
  fdd?: FddResult[];
  energy?: any;
  dewa_tariff?: DewaTariff;
  fetched_at?: string;
  [k: string]: any;
}
export interface SessionEvent { event_type: 'login' | 'logout' | 'page_view'; user_id?: string; email?: string; role?: string; path?: string; meta?: Record<string, any>; }
export interface JciTestRequest { host: string; username: string; password: string; version?: string; }
export interface JciTestResponse { status: 'connected' | 'failed' | 'saved'; response_ms?: number; error?: string; version?: string; message?: string; }

function normalizeHealth(raw: Record<string, unknown>): ApiHealth {
  return {
    status: String(raw.status ?? 'unknown'),
    version: raw.version as string | undefined,
    uptime_s: Number(raw.uptime_seconds ?? raw.uptime_s ?? 0),
    response_ms: raw.response_ms as number | undefined,
    health_score: raw.health_score as number | undefined,
  };
}

function normalizeProtocols(raw: Record<string, unknown>): ConnectionsResponse {
  const keyed = raw as ConnectionsResponse;
  if (keyed.metasys?.status || keyed.influxdb?.status) return keyed;

  const out: ConnectionsResponse = {};
  const list = (raw.protocols as Array<Record<string, unknown>> | undefined) ?? [];
  for (const item of list) {
    const key = String(item.key ?? item.name ?? '')
      .toLowerCase()
      .replace(/\s+rest$/i, '')
      .replace(/\s+/g, '');
    if (!key) continue;
    out[key] = {
      name: String(item.name ?? key),
      status: String(item.status ?? 'unknown'),
      last_seen: String(item.last_seen_human ?? item.last_seen ?? '—'),
      data_points: item.data_points as number | undefined,
      response_ms: item.response_ms as number | undefined,
    };
  }

  const legacy = raw as { jci_metasys?: string; bacnet?: string; modbus?: string; mqtt?: string };
  if (legacy.jci_metasys && !out.metasys) {
    out.metasys = { name: 'Metasys REST', status: legacy.jci_metasys };
  }
  if (legacy.bacnet && !out.bacnet) out.bacnet = { name: 'BACnet', status: legacy.bacnet };
  if (legacy.modbus && !out.modbus) out.modbus = { name: 'Modbus', status: legacy.modbus };

  return out;
}

function normalizeHistory(raw: unknown): Array<{ timestamp: string; response_ms: number }> {
  if (Array.isArray(raw)) return raw as Array<{ timestamp: string; response_ms: number }>;
  const obj = raw as { data?: unknown; history?: unknown };
  if (Array.isArray(obj.data)) return obj.data as Array<{ timestamp: string; response_ms: number }>;
  if (Array.isArray(obj.history)) return obj.history as Array<{ timestamp: string; response_ms: number }>;
  return [];
}

function normalizeLogs(raw: unknown): Array<{ timestamp: string; level: string; message: string }> {
  if (Array.isArray(raw)) return raw as Array<{ timestamp: string; level: string; message: string }>;
  const obj = raw as { logs?: unknown };
  if (Array.isArray(obj.logs)) return obj.logs as Array<{ timestamp: string; level: string; message: string }>;
  return [];
}

function normalizePipeline(raw: unknown): Array<{ name: string; interval: string; last_run: string; status: string }> {
  const mapJob = (j: Record<string, unknown>) => ({
    name: String(j.name ?? ''),
    interval: String(j.interval ?? ''),
    last_run: String(j.last_run_human ?? j.last_run ?? ''),
    status: String(j.status ?? 'unknown'),
  });
  if (Array.isArray(raw)) return raw.map(mapJob);
  const obj = raw as { jobs?: unknown };
  if (Array.isArray(obj.jobs)) return obj.jobs.map(mapJob);
  return [];
}

// ---------- Endpoints ----------
export const apiGetHealth = async () => normalizeHealth(await get<Record<string, unknown>>('/health'));
export const apiGetHealthHistory = async () => normalizeHistory(await get<unknown>('/health/history?hours=24'));
export const apiGetHealthLogs = async (limit = 10) => normalizeLogs(await get<unknown>(`/health/logs?limit=${limit}`));
export const apiGetHealthPipeline = async () => normalizePipeline(await get<unknown>('/health/pipeline'));
export const apiGetHealthProtocols = async () => normalizeProtocols(await get<Record<string, unknown>>('/health/protocols'));
export const apiGetSiteMetadata = () => get<SiteMetadata>('/site/metadata');
export const apiGetConnections = async () => {
  const raw = await get<Record<string, unknown>>('/health/connections');
  return {
    ingest_api: raw.ingest_api ? { name: 'Ingest API', status: raw.ingest_api ? 'connected' : 'not_configured' } : undefined,
    alert_webhook: raw.alert_webhook ? { name: 'Alert Webhook', status: raw.alert_webhook ? 'connected' : 'not_configured' } : undefined,
    ...normalizeProtocols(raw),
  } satisfies ConnectionsResponse;
};
export const apiGetBuildings = () => get<Building[]>('/buildings');
export const apiGetBuildingLive = (id: string) => get<LiveBuildingData>(`/buildings/${id}/live`);
export const apiGetEnergyConsumption = (b?: string) => get<EnergyConsumptionPoint[]>(`/energy/consumption${b ? `?building_id=${b}` : ''}`);
export const apiGetEnergyForecast = (b?: string) => get<EnergyForecastPoint[]>(`/energy/forecast${b ? `?building_id=${b}` : ''}`);
export const apiGetDewaTariff = () => get<DewaTariff>('/energy/dewa-tariff');
export const apiGetEnergySavings = (b?: string) => get<EnergySavings>(`/energy/savings${b ? `?building_id=${b}` : ''}`);
export const apiGetEquipment = (b?: string) => get<Equipment[]>(`/equipment${b ? `?building_id=${b}` : ''}`);
export const apiGetAlerts = () => get<AlertItem[]>('/alerts');
export const apiGetFddResults = () => get<FddResult[]>('/alerts/fdd');
export const apiGetPrayerTimes = () => get<PrayerTimes>('/gcc/prayer-times');
export const apiGetRamadanMode = () => get<RamadanMode>('/gcc/ramadan-mode');
export const apiGetSandstormAlert = () => get<SandstormAlert>('/gcc/sandstorm-alert');
export const apiGetModuleData = (slug: string) => get<ModuleData>(`/modules/${encodeURIComponent(slug)}/data?building_id=burj-khalifa-01`);
export const apiGetModuleCategories = () => get<Array<{ category: string; count: number }>>('/modules/categories');
export const apiGetBuildingMetrics = (id: string, period = '24h') =>
  get<{ building_id: string; period: string; metrics: Array<{ timestamp: string; value: number; metric: string }> }>(
    `/buildings/${id}/metrics?period=${period}`,
  );
export const apiAcknowledgeAlert = (id: string, notes?: string) =>
  post<{ success: boolean }>(`/alerts/${id}/acknowledge`, { notes });

/** Subscribe to SSE live building stream. Returns cleanup function. */
export function subscribeBuildingLiveStream(
  buildingId: string,
  onMessage: (data: LiveBuildingData) => void,
  onError?: (err: Event) => void,
): () => void {
  if (!API_URL) return () => undefined;
  const url = `${API_URL}/api/v1/buildings/${buildingId}/live/stream`;
  const source = new EventSource(url);
  source.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data) as LiveBuildingData);
    } catch {
      /* ignore malformed frames */
    }
  };
  source.onerror = (ev) => onError?.(ev);
  return () => source.close();
}

export const apiPostSessionEvent = (ev: SessionEvent) => post<{ ok: boolean }>('/sessions/events', ev);
export const apiJciTestConnection = (req: JciTestRequest) => post<JciTestResponse>('/jci/test-connection', req);
export const apiJciSaveCredentials = (req: JciTestRequest) => post<JciTestResponse>('/jci/save-credentials', req);
export const apiJciNetworkDiagnostic = (req: JciTestRequest) => post<{ checks: Array<{ step: string; status: string; detail: string }>; overall: string; summary: string }>('/jci/network-diagnostic', req);
