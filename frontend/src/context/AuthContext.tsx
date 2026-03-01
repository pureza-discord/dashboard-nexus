import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, clearToken, setToken } from '../services/api'

export interface BillingSnapshot {
  plan_type: string
  is_admin?: boolean
  leads_limit_mensal: number | null
  leads_used_current_month: number
  available_leads?: number | string | null
  external_queries_limit_mensal: number | null
  external_queries_used_current_month: number
  plan_reset_date: string | null
  allow_csv_export: boolean
  allow_multi_user: boolean
  credits_balance?: number
}

export interface AuthUser {
  id: string
  email: string
  full_name?: string | null
  plan_type: string
  is_admin?: boolean
  email_verified?: boolean
  credits_balance?: number
  billing: BillingSnapshot
  stripe_customer_id?: string | null
  stripe_subscription_id?: string | null
}

interface AuthState {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  reloadUser: () => Promise<void>
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
  reloadUser: async () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const reloadUser = async () => {
    const current = await api<AuthUser>('/api/auth/me', { skipAuthRedirect: true })
    setUser(current)
  }

  useEffect(() => {
    reloadUser()
      .catch(() => {
        clearToken()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const res = await api<{ access_token: string; user: AuthUser }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      skipAuthRedirect: true,
    })
    if (res.access_token) setToken(res.access_token)
    setUser(res.user)
  }

  const logout = async () => {
    try {
      await api('/api/auth/logout', { method: 'POST', skipAuthRedirect: true })
    } catch {
      // ignore network errors during logout
    }
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, reloadUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
