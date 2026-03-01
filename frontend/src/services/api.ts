const TOKEN_KEY = 'nexus_token'
const RAW_API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL || '').trim()
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '')

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ApiOptions extends Omit<RequestInit, 'headers'> {
  headers?: Record<string, string>
  skipAuthRedirect?: boolean
}

function toAbsoluteUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

function parseErrorMessage(payload: unknown): string {
  if (!payload) return 'Request failed'
  if (typeof payload === 'string') return payload
  if (typeof payload === 'object' && payload !== null) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) return detail
    const message = (payload as { message?: unknown }).message
    if (typeof message === 'string' && message.trim()) return message
  }
  return 'Request failed'
}

function isLoginRequest(url: string): boolean {
  return /\/api\/auth\/login$/i.test(url)
}

function redirectToLogin(): void {
  if (window.location.pathname === '/login') return
  const next = encodeURIComponent(`${window.location.pathname}${window.location.search}`)
  window.location.assign(`/login?next=${next}`)
}

async function request<T>(
  url: string,
  opts: ApiOptions = {},
  withAuth: boolean,
): Promise<T> {
  const token = withAuth ? getToken() : ''
  const absoluteUrl = toAbsoluteUrl(url)

  let res: Response
  try {
    res = await fetch(absoluteUrl, {
      ...opts,
      credentials: 'include',
      headers: {
        ...(opts.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(opts.headers || {}),
      },
    })
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Request failed'
    throw new ApiError(
      msg.includes('fetch') || msg.includes('Network') || msg.includes('Failed')
        ? 'Não foi possível conectar ao servidor. Verifique se o backend está rodando.'
        : msg,
      0
    )
  }

  let payload: unknown = null
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    payload = await res.json().catch(() => null)
  } else {
    payload = await res.text().catch(() => '')
  }

  if (!res.ok) {
    if (res.status === 401 && withAuth && !opts.skipAuthRedirect && !isLoginRequest(absoluteUrl)) {
      clearToken()
      redirectToLogin()
    }
    throw new ApiError(parseErrorMessage(payload), res.status)
  }

  return payload as T
}

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function api<T = unknown>(url: string, opts: ApiOptions = {}): Promise<T> {
  return request<T>(url, opts, true)
}

export function apiPublic<T = unknown>(url: string, opts: ApiOptions = {}): Promise<T> {
  return request<T>(url, opts, false)
}
