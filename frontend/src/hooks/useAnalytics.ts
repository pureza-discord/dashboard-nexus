import { useState, useEffect } from 'react'
import { api } from '../services/api'

export function useAnalytics() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api('/api/analytics')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return { data, loading }
}
