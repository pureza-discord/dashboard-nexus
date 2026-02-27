import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { api, setToken, clearToken, getToken } from '../services/api'

interface AuthState {
  user: string | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    api<{ username: string }>('/api/me')
      .then((d) => setUser(d.username))
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string) => {
    const res = await api<{ token: string }>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    setToken(res.token)
    setUser(username)
  }

  const logout = () => {
    fetch('/api/logout', { method: 'POST' })
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
