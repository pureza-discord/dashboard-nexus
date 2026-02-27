const TOKEN_KEY = 'nexus_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function api<T = any>(url: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(url, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...((opts.headers as Record<string, string>) || {}),
    },
  })

  if (res.status === 401) {
    clearToken()
    window.location.href = '/login'
    throw new Error('Session expired')
  }

  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Request failed')
  return data as T
}
