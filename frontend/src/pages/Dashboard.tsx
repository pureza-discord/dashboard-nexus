import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import StatsCards from '../components/layout/StatsCards'
import FunnelChart from '../components/charts/FunnelChart'
import DonutChart from '../components/charts/DonutChart'
import AIChatPanel from '../components/ai/AIChatPanel'
import { useLeads } from '../hooks/useLeads'
import { useAnalytics } from '../hooks/useAnalytics'

export default function Dashboard() {
  const { stats, reload } = useLeads()
  const { data: analytics, reload: reloadAnalytics } = useAnalytics()
  const navigate = useNavigate()

  const manualReload = async () => {
    try {
      await Promise.all([reload(), reloadAnalytics()])
    } catch {
      // hooks handle errors
    }
  }

  const funnelData = useMemo(() => {
    if (!analytics?.pipeline) return []
    return analytics.pipeline.map((p) => ({
      stage: p.label,
      count: p.count,
    }))
  }, [analytics])

  const funnelTotal = useMemo(() => {
    return funnelData.reduce((sum, stage) => sum + stage.count, 0)
  }, [funnelData])

  const donutSegments = useMemo(() => {
    return [
      { label: 'Novos', value: stats.novos ?? 0, color: '#60a5fa' },
      { label: 'Contatados', value: stats.contatados ?? 0, color: '#a1a1aa' },
      { label: 'Fechados', value: stats.fechados ?? 0, color: '#22c55e' },
      { label: 'Perdidos', value: stats.perdidos ?? 0, color: '#ef4444' },
    ]
  }, [stats])

  const donutTotal = useMemo(() => {
    return donutSegments.reduce((sum, segment) => sum + segment.value, 0)
  }, [donutSegments])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">Dashboard</h1>
        <p className="mt-1 text-[13px] text-nexus-muted">
          Visao geral das suas oportunidades.
        </p>
      </div>

      <StatsCards
        stats={stats}
        leadsThisMonth={analytics?.leads_this_month ?? 0}
        onFilter={(status) => {
          navigate(`/app/leads?status=${status}`)
        }}
      />

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <DonutChart segments={donutSegments} total={donutTotal} />
          <FunnelChart data={funnelData} total={funnelTotal} />
        </div>

        <AIChatPanel
          onDataChanged={async () => {
            await manualReload()
          }}
        />
      </div>
    </div>
  )
}
