import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../services/api'

interface Filters {
  status: string
  pais: string
  search: string
  page: number
  per_page: number
  sort_by: string
  sort_dir: string
}

export function useLeads() {
  const [leads, setLeads] = useState<any[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [countries, setCountries] = useState<string[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<Filters>({
    status: 'novo', pais: 'todos', search: '', page: 1, per_page: 50, sort_by: 'id', sort_dir: 'desc',
  })
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        status: filters.status,
        pais: filters.pais,
        search: filters.search,
        page: String(filters.page),
        per_page: String(filters.per_page),
        sort_by: filters.sort_by,
        sort_dir: filters.sort_dir,
      })
      const data = await api(`/api/leads?${params}`)
      setLeads(data.leads)
      setStats(data.stats)
      setCountries(data.countries)
      setTotal(data.total)
      setPages(data.pages)
    } catch {
      // handled by api interceptor
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  useEffect(() => {
    timerRef.current = setInterval(load, 30_000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [load])

  const setFilter = useCallback((key: keyof Filters, value: string | number) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value,
      ...(key !== 'page' ? { page: 1 } : {}),
    }))
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
    leads, stats, countries, total, pages, loading, filters,
    setFilter, toggleSort, reload: load,
  }
}
