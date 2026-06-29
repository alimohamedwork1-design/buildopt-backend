/**
 * Prefer live API data when enabled; keep mocks as offline fallback.
 * Drop into: src/lib/data-source.ts
 */
import { isApiEnabled } from "@/lib/buildopt-api";

export function pickApiOrMock<T>(apiValue: T | undefined | null, mockValue: T): T {
  if (isApiEnabled() && apiValue !== undefined && apiValue !== null) {
    return apiValue;
  }
  return mockValue;
}

export function pickApiArray<T>(apiValue: T[] | undefined, mockValue: T[]): T[] {
  if (isApiEnabled() && apiValue && apiValue.length > 0) {
    return apiValue;
  }
  return mockValue;
}
