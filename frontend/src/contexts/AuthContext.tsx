/**
 * Auth context — provides login/logout/user state to the entire app.
 *
 * JWT is stored in React state (in-memory only). On page refresh the
 * user must re-login — this is intentional per security practice.
 * No localStorage/sessionStorage/cookies are used for token storage.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { UserResponse } from "@/api/types";
import * as api from "@/api/client";

interface AuthContextValue {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const tokenResponse = await api.login(username, password);
      api.setToken(tokenResponse.access_token);

      const me = await api.getMe();
      setUser(me);
    } catch (err) {
      api.setToken(null);
      setUser(null);
      if (err instanceof api.ApiError) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred");
      }
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    api.setToken(null);
    setUser(null);
    setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      error,
      login,
      logout,
    }),
    [user, isLoading, error, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
