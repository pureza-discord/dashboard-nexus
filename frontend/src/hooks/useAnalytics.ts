import { useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'

export interface AnalyticsPayload {
  leads_this_month: number
  total_leads: number
  potential_revenue: number
  expected_revenue: number
  conversion_rate: number
  pipeline: { stage: string; label: string; count: number }[]
  conversion_by_niche: { nicho: string; total: number; closed: number; conversion_rate: number }[]
  conversion_by_city: { cidade: string; total: number; closed: number; conversion_rate: number }[]
  revenue_by_month: { month: string; revenue: number }[]
}

export function useAnalytics() {
  const [data, setData] = useState<AnalyticsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setError('')
      const payload = await api<AnalyticsPayload>('/api/analytics/overview')
      setData(payload)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar analytics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return { data, loading, error, reload: load }
}
