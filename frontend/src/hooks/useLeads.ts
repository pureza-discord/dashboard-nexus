import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../services/api'

export type LeadStatus = 'novos' | 'contatados' | 'proposta' | 'fechados' | 'perdidos'

export interface LeadItem {
  id: string
  _id: string
  status: LeadStatus
  _status: LeadStatus
  empresa: string
  telefone?: string
  email?: string
  site?: string
  cidade?: string
  pais?: string
  nicho?: string
  origem?: string
  score: number
  ticket_estimado: number
  chance_fechamento: number
  ultimo_contato?: string | null
  proximo_follow_up?: string | null
  observacoes?: string | null
  created_at?: string
  updated_at?: string
  _created?: string
  _updated?: string
}

interface LeadsResponse {
  leads: LeadItem[]
  stats: Record<string, number>
  countries: string[]
  total: number
  pages: number
}

export interface LeadFilters {
  status: string
  pais: string
  cidade: string
  nicho: string
  search: string
  page: number
  per_page: number
  sort_by: string
  sort_dir: string
}

const initialFilters: LeadFilters = {
  status: 'todos',
  pais: '',
  cidade: '',
  nicho: '',
  search: '',
  page: 1,
  per_page: 50,
  sort_by: 'created_at',
  sort_dir: 'desc',
}

const REFRESH_DEFAULT_MS = 30000
const REFRESH_STORAGE_KEY = 'nexus_refresh_ms'
const LIVE_STORAGE_KEY = 'nexus_live_mode'

function readLiveMode(): boolean {
  try {
    const raw = window.localStorage.getItem(LIVE_STORAGE_KEY)
    if (!raw) return true
    return raw !== '0'
  } catch {
    return true
  }
}

function readRefreshMs(): number {
  try {
    const raw = Number(window.localStorage.getItem(REFRESH_STORAGE_KEY) || REFRESH_DEFAULT_MS)
    if (!Number.isFinite(raw) || raw < 10000) return REFRESH_DEFAULT_MS
    return raw
  } catch {
    return REFRESH_DEFAULT_MS
  }
}

export function useLeads() {
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [countries, setCountries] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState<LeadFilters>(initialFilters)
  const [liveMode, setLiveMode] = useState<boolean>(readLiveMode)
  const [refreshMs, setRefreshMs] = useState<number>(readRefreshMs)
  const [lastLoadedAt, setLastLoadedAt] = useState<number>(Date.now())
  const timerRef = useRef<number | null>(null)

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      status: filters.status,
      pais: filters.pais,
      cidade: filters.cidade,
      nicho: filters.nicho,
      search: filters.search,
      page: String(filters.page),
      per_page: String(filters.per_page),
      sort_by: filters.sort_by,
      sort_dir: filters.sort_dir,
    })
    return params.toString()
  }, [filters])

  const load = useCallback(async () => {
    try {
      setError('')
      const data = await api<LeadsResponse>(`/api/leads?${queryString}`)
      setLeads(data.leads || [])
      setStats(data.stats || {})
      setCountries(data.countries || [])
      setTotal(data.total || 0)
      setPages(data.pages || 1)
      setLastLoadedAt(Date.now())
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar leads')
    } finally {
      setLoading(false)
    }
  }, [queryString])

  useEffect(() => {
    setLoading(true)
    void load()
  }, [load])

  useEffect(() => {
    if (!liveMode) return
    timerRef.current = window.setInterval(() => {
      if (!document.hidden) {
        void load()
      }
    }, refreshMs)
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current)
    }
  }, [load, liveMode, refreshMs])

  useEffect(() => {
    try {
      window.localStorage.setItem(LIVE_STORAGE_KEY, liveMode ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  }, [liveMode])

  useEffect(() => {
    try {
      window.localStorage.setItem(REFRESH_STORAGE_KEY, String(refreshMs))
    } catch {
      // ignore storage errors
    }
  }, [refreshMs])

  const setFilter = useCallback((key: keyof LeadFilters, value: string | number) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      ...(key !== 'page' ? { page: 1 } : {}),
    }))
  }, [])

  const resetFilters = useCallback(() => {
    setFilters(initialFilters)
  }, [])

  const toggleSort = useCallback((col: string) => {
    setFilters((prev) => ({
      ...prev,
      sort_by: col,
      sort_dir: prev.sort_by === col && prev.sort_dir === 'desc' ? 'asc' : 'desc',
      page: 1,
    }))
  }, [])

  return {
    leads,
    stats,
    countries,
    total,
    pages,
    loading,
    error,
    filters,
    setFilter,
    resetFilters,
    toggleSort,
    reload: load,
    liveMode,
    setLiveMode,
    refreshMs,
    setRefreshMs,
    lastLoadedAt,
  }
}
