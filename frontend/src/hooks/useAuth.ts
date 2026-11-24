import { createContext, useContext, useState, useCallback, ReactNode, createElement } from 'react';
import { api } from '../services/api';
import type { DoctorUser } from '../types';

interface AuthContextValue {
  user: DoctorUser | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<DoctorUser | null>(() => {
    const stored = localStorage.getItem('user');
    return stored ? JSON.parse(stored) : null;
  });
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const token = await api.login({ username, password });
      localStorage.setItem('access_token', token.access_token);
      const me = await api.getMe();
      localStorage.setItem('user', JSON.stringify(me));
      setUser(me);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setUser(null);
  }, []);

  return createElement(AuthContext.Provider, { value: { user, isLoading, login, logout, isAuthenticated: !!user } }, children);
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
