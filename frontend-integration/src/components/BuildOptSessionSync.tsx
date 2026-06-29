/**
 * Wrap protected routes to sync login/page_view/logout with Railway backend.
 * Drop into: src/components/BuildOptSessionSync.tsx
 */
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { trackLogin, trackLogout, usePageViewTracking } from "@/hooks/useBuildOptApi";

export function BuildOptSessionSync({ children }: { children: React.ReactNode }) {
  const { user, roles } = useAuth();
  const role = roles?.[0];

  usePageViewTracking(user?.id, role);

  useEffect(() => {
    if (!user) return;
    trackLogin({ id: user.id, email: user.email }, role).catch(() => undefined);
  }, [user?.id, user?.email, role]);

  useEffect(() => {
    if (!user) return;
    return () => {
      trackLogout(user.id).catch(() => undefined);
    };
  }, [user?.id]);

  return <>{children}</>;
}
