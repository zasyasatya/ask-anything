"use client";
/* Sesi login untuk seluruh UI.
 *
 * Sumber kebenaran ada di backend (cookie HttpOnly `ask_session`); provider ini
 * hanya *membaca* siapa yang sedang login (`GET /api/auth/me`) dan membagikan
 * perannya ke komponen lain — termasuk `capabilities` (mode/tool yang boleh,
 * akses model offline, cakupan task). UI memakainya untuk menyembunyikan yang
 * memang akan ditolak server; penegakan tetap di backend.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authLogout, authMe } from "./api";
import type { AuthUser, Capabilities } from "./types";

interface AuthState {
  user: AuthUser | null;
  capabilities: Capabilities | null;
  /** true = mode `ASK_AUTH_MODE=open` (tanpa login, demo/test). */
  anonymous: boolean;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<AuthUser | null>;
  logout: () => Promise<void>;
}

const FALLBACK_CAPS: Capabilities = {
  role: "member",
  is_admin: false,
  dashboard: "/",
  modes: { text: true, diagram: true, rag: true },
  tools: {},
  allow_offline_models: false,
  allow_provider_settings: false,
  allow_admin_console: false,
  allow_rag_upload: false,
  allow_task_write: false,
  tasks_scope: "assigned",
  chat_provider: "openai",
};

const AuthContext = createContext<AuthState>({
  user: null,
  capabilities: null,
  anonymous: false,
  loading: true,
  error: null,
  refresh: async () => null,
  logout: async () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [anonymous, setAnonymous] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await authMe();
      setUser(data.user);
      setAnonymous(Boolean(data.anonymous));
      setError(null);
      return data.user;
    } catch (e) {
      // 401 = belum login (bukan error aplikasi) — halaman /login yang urus.
      setUser(null);
      setError(String(e).includes("401") ? null : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authLogout();
    } catch {
      /* sesi mungkin sudah mati di server — tetap bersihkan state lokal */
    }
    setUser(null);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const capabilities = useMemo<Capabilities | null>(
    () => user?.capabilities ?? (anonymous ? { ...FALLBACK_CAPS, role: "admin", is_admin: true } : null),
    [user, anonymous]
  );

  const value = useMemo<AuthState>(
    () => ({ user, capabilities, anonymous, loading, error, refresh, logout }),
    [user, capabilities, anonymous, loading, error, refresh, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

/** Izin efektif; selalu ada nilainya supaya komponen tidak perlu null-check. */
export function useCapabilities(): Capabilities {
  const { capabilities } = useAuth();
  return capabilities ?? FALLBACK_CAPS;
}
