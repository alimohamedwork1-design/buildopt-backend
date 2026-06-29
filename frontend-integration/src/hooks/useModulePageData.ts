/**
 * Universal hook for any module page — auto-fetches backend data for current route.
 * Drop into: src/hooks/useModulePageData.ts
 */
import { useLocation } from "react-router-dom";
import { useModuleData } from "@/hooks/useBuildOptApi";

export function useModulePageData(buildingId?: string) {
  const { pathname } = useLocation();
  const slug = pathname.replace(/^\//, "") || "overview";
  const { data, isLoading, error, refetch, isFetching } = useModuleData(slug, buildingId);

  return {
    data,
    isLoading,
    isFetching,
    error,
    refetch,
    slug,
    path: pathname,
  };
}
