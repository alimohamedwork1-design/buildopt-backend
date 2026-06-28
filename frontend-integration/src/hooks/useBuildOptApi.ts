/**
 * React Query hooks for BuildOpt FastAPI backend.
 * Drop into: src/hooks/useBuildOptApi.ts
 */

import { useQuery } from "@tanstack/react-query";
import {
  getAlerts,
  getBuildingLive,
  getBuildings,
  getDewaTariff,
  getEnergyConsumption,
  getEnergyForecast,
  getEnergySavings,
  getEquipment,
  getFddResults,
  getHealth,
  getPrayerTimes,
  getRamadanMode,
  getSandstormAlert,
  isApiEnabled,
} from "@/lib/api-client";

const REFETCH_MS = 30_000;

export function useApiHealth() {
  return useQuery({
    queryKey: ["buildopt", "health"],
    queryFn: getHealth,
    enabled: isApiEnabled(),
    refetchInterval: REFETCH_MS,
  });
}

export function useBuildings() {
  return useQuery({
    queryKey: ["buildopt", "buildings"],
    queryFn: getBuildings,
    enabled: isApiEnabled(),
    staleTime: REFETCH_MS,
  });
}

export function useBuildingLive(buildingId = "burj-khalifa-01") {
  return useQuery({
    queryKey: ["buildopt", "live", buildingId],
    queryFn: () => getBuildingLive(buildingId),
    enabled: isApiEnabled(),
    refetchInterval: 5_000,
  });
}

export function useEnergyConsumption() {
  return useQuery({
    queryKey: ["buildopt", "energy", "consumption"],
    queryFn: getEnergyConsumption,
    enabled: isApiEnabled(),
    refetchInterval: REFETCH_MS,
  });
}

export function useEnergyForecast(buildingId = "burj-khalifa-01") {
  return useQuery({
    queryKey: ["buildopt", "energy", "forecast", buildingId],
    queryFn: () => getEnergyForecast(buildingId),
    enabled: isApiEnabled(),
    staleTime: 60_000,
  });
}

export function useDewaTariff() {
  return useQuery({
    queryKey: ["buildopt", "energy", "dewa"],
    queryFn: getDewaTariff,
    enabled: isApiEnabled(),
    staleTime: 300_000,
  });
}

export function useEnergySavings() {
  return useQuery({
    queryKey: ["buildopt", "energy", "savings"],
    queryFn: getEnergySavings,
    enabled: isApiEnabled(),
    refetchInterval: REFETCH_MS,
  });
}

export function useEquipment(buildingId?: string) {
  return useQuery({
    queryKey: ["buildopt", "equipment", buildingId ?? "all"],
    queryFn: () => getEquipment(buildingId),
    enabled: isApiEnabled(),
    refetchInterval: REFETCH_MS,
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: ["buildopt", "alerts"],
    queryFn: getAlerts,
    enabled: isApiEnabled(),
    refetchInterval: 15_000,
  });
}

export function useFddResults() {
  return useQuery({
    queryKey: ["buildopt", "fdd"],
    queryFn: getFddResults,
    enabled: isApiEnabled(),
    refetchInterval: REFETCH_MS,
  });
}

export function usePrayerTimes() {
  return useQuery({
    queryKey: ["buildopt", "gcc", "prayer"],
    queryFn: getPrayerTimes,
    enabled: isApiEnabled(),
    staleTime: 3_600_000,
  });
}

export function useRamadanMode() {
  return useQuery({
    queryKey: ["buildopt", "gcc", "ramadan"],
    queryFn: getRamadanMode,
    enabled: isApiEnabled(),
    staleTime: 3_600_000,
  });
}

export function useSandstormAlert() {
  return useQuery({
    queryKey: ["buildopt", "gcc", "sandstorm"],
    queryFn: getSandstormAlert,
    enabled: isApiEnabled(),
    refetchInterval: REFETCH_MS,
  });
}
