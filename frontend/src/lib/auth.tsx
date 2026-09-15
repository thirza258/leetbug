import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, post, setCsrf } from './api';
import type { Session, User } from '../types';

interface Auth {
  user: User | null; loading: boolean; error: Error | null;
  authenticate: (path: 'login' | 'register', data: Record<string, string>) => Promise<void>;
  logout: () => Promise<void>;
}
const AuthContext = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const session = useQuery({ queryKey: ['session'], queryFn: async () => {
    const result = await api<Session>('/auth/me'); setCsrf(result.csrf_token); return result;
  }, staleTime: 60_000, retry: 1 });
  async function authenticate(path: 'login' | 'register', data: Record<string, string>) {
    const result = await post<Session>(`/auth/${path}`, data);
    await client.cancelQueries();
    setCsrf(result.csrf_token);
    // Keep the active session observer attached while discarding the previous user's data.
    client.removeQueries({ predicate: query => query.queryKey[0] !== 'session' });
    client.setQueryData(['session'], result);
  }
  async function logout() {
    await post('/auth/logout');
    await client.cancelQueries();
    setCsrf(null);
    client.removeQueries({ predicate: query => query.queryKey[0] !== 'session' });
    client.setQueryData(['session'], { user: null, csrf_token: null });
  }
  return <AuthContext.Provider value={{ user: session.data?.user ?? null, loading: session.isPending,
    error: session.error, authenticate, logout }}>{children}</AuthContext.Provider>;
}
// The hook shares the provider's module by design.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('AuthProvider is required');
  return value;
}
