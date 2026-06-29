/**
 * React Query hooks for all BuildOpt backend endpoints
 * Drop into: src/hooks/useBuildOptApi.ts
 */

import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { useEffect } from "react";
import {
  acknowledgeAlert,
  getAlerts,
  getBuildingLive,
  getBuildingMetrics,
  getBuildings,
  getConnections,
  getDewaTariff,
  getEnergyConsumption,
  getEnergyForecast,
  getEnergySavings,
  getEquipment,
  getFddResults,
  getHealth,
  getConnections,
  getProtocolHealth,
  getHealthHistory,
  getHealthLogs,
  getHealthPipeline,
  getModuleData,
  getPrayerTimes,
  getRamadanMode,
  getSandstormAlert,
  getSiteMetadata,
  getDefaultBuildingId,
  isApiEnabled,
  trackSessionEvent,
  type SessionEventPayload,
} from "@/lib/buildopt-api";

const LIVE_MS = 5_000;
const ALERTS_MS = 15_000;
const HEALTH_MS = 30_000;
const ENERGY_MS = 60_000;
const MODULE_MS = 30_000;

export function useSiteMetadata() {
  return useQuery({ queryKey: ["buildopt", "site"], queryFn: getSiteMetadata, enabled: isApiEnabled(), staleTime: 300_000 });
}

export function useApiHealth() {
  return useQuery({ queryKey: ["buildopt", "health"], queryFn: getHealth, enabled: isApiEnabled(), refetchInterval: HEALTH_MS });
}

export function useConnections() {
  return useQuery({ queryKey: ["buildopt", "connections"], queryFn: getConnections, enabled: isApiEnabled(), refetchInterval: HEALTH_MS });
}

export function useProtocolHealth() {
  return useQuery({ queryKey: ["buildopt", "protocols"], queryFn: getProtocolHealth, enabled: isApiEnabled(), refetchInterval: HEALTH_MS });
}

export function useHealthHistory(hours = 24) {
  return useQuery({
    queryKey: ["buildopt", "health-history", hours],
    queryFn: () => getHealthHistory(hours),
    enabled: isApiEnabled(),
    staleTime: 60_000,
  });
}

export function useHealthLogs(limit = 10) {
  return useQuery({
    queryKey: ["buildopt", "health-logs", limit],
    queryFn: () => getHealthLogs(limit),
    enabled: isApiEnabled(),
    refetchInterval: HEALTH_MS,
  });
}

export function useHealthPipeline() {
  return useQuery({
    queryKey: ["buildopt", "health-pipeline"],
    queryFn: getHealthPipeline,
    enabled: isApiEnabled(),
    refetchInterval: HEALTH_MS,
  });
}

export function useBuildings() {
  return useQuery({ queryKey: ["buildopt", "buildings"], queryFn: getBuildings, enabled: isApiEnabled(), staleTime: 60_000 });
}

export function useBuildingLive(buildingId?: string) {
  const id = buildingId ?? getDefaultBuildingId();
  return useQuery({
    queryKey: ["buildopt", "live", id],
    queryFn: () => getBuildingLive(id),
    enabled: isApiEnabled(),
    refetchInterval: LIVE_MS,
  });
}

export function useBuildingMetrics(buildingId?: string, period = "24h") {
  const id = buildingId ?? getDefaultBuildingId();
  return useQuery({
    queryKey: ["buildopt", "metrics", id, period],
    queryFn: () => getBuildingMetrics(id, period),
    enabled: isApiEnabled(),
    staleTime: 60_000,
  });
}

export function useModuleData(slug?: string, buildingId?: string) {
  const location = useLocation();
  const pathSlug = slug ?? location.pathname.replace(/^\//, "") || "overview";
  const id = buildingId ?? getDefaultBuildingId();
  return useQuery({
    queryKey: ["buildopt", "module", pathSlug, id],
    queryFn: () => getModuleData(pathSlug === "" ? "overview" : pathSlug, id),
    enabled: isApiEnabled(),
    refetchInterval: MODULE_MS,
  });
}

export function useEnergyConsumption(buildingId?: string) {
  return useQuery({
    queryKey: ["buildopt", "energy", "consumption", buildingId],
    queryFn: () => getEnergyConsumption(buildingId),
    enabled: isApiEnabled(),
    refetchInterval: ENERGY_MS,
  });
}

export function useEnergyForecast(buildingId?: string) {
  return useQuery({
    queryKey: ["buildopt", "energy", "forecast", buildingId],
    queryFn: () => getEnergyForecast(buildingId),
    enabled: isApiEnabled(),
    staleTime: ENERGY_MS,
  });
}

export function useDewaTariff() {
  return useQuery({ queryKey: ["buildopt", "dewa"], queryFn: getDewaTariff, enabled: isApiEnabled(), staleTime: 300_000 });
}

export function useEnergySavings() {
  return useQuery({ queryKey: ["buildopt", "savings"], queryFn: getEnergySavings, enabled: isApiEnabled(), refetchInterval: ENERGY_MS });
}

export function useEquipment(buildingId?: string) {
  return useQuery({
    queryKey: ["buildopt", "equipment", buildingId ?? "all"],
    queryFn: () => getEquipment(buildingId),
    enabled: isApiEnabled(),
    refetchInterval: HEALTH_MS,
  });
}

export function useAlerts() {
  return useQuery({ queryKey: ["buildopt", "alerts"], queryFn: getAlerts, enabled: isApiEnabled(), refetchInterval: ALERTS_MS });
}

export function useFddResults() {
  return useQuery({ queryKey: ["buildopt", "fdd"], queryFn: getFddResults, enabled: isApiEnabled(), refetchInterval: HEALTH_MS });
}

export function usePrayerTimes() {
  return useQuery({ queryKey: ["buildopt", "prayer"], queryFn: getPrayerTimes, enabled: isApiEnabled(), staleTime: 3_600_000 });
}

export function useRamadanMode() {
  return useQuery({ queryKey: ["buildopt", "ramadan"], queryFn: getRamadanMode, enabled: isApiEnabled(), staleTime: 3_600_000 });
}

export function useSandstormAlert() {
  return useQuery({ queryKey: ["buildopt", "sandstorm"], queryFn: getSandstormAlert, enabled: isApiEnabled(), refetchInterval: HEALTH_MS });
}

export function useAcknowledgeAlert() {
  return useMutation({ mutationFn: ({ id, notes }: { id: string; notes?: string }) => acknowledgeAlert(id, notes) });
}

/** Track page views automatically on route change */
export function usePageViewTracking(userId?: string, role?: string) {
  const location = useLocation();
  useEffect(() => {
    if (!isApiEnabled()) return;
    trackSessionEvent({
      event_type: "page_view",
      user_id: userId,
      role,
      module_path: location.pathname,
      metadata: { title: document.title },
    }).catch(() => undefined);
  }, [location.pathname, userId, role]);
}

/** Call on Supabase login success */
export async function trackLogin(user: { id: string; email?: string }, role?: string) {
  if (!isApiEnabled()) return;
  const payload: SessionEventPayload = {
    event_type: "login",
    user_id: user.id,
    email: user.email,
    role,
    metadata: { provider: "supabase" },
  };
  await trackSessionEvent(payload);
}

export async function trackLogout(userId?: string) {
  if (!isApiEnabled()) return;
  await trackSessionEvent({ event_type: "logout", user_id: userId });
}
