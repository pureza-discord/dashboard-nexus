import { useMemo } from 'react'
import StatsCards from '../components/layout/StatsCards'
import FunnelChart from '../components/charts/FunnelChart'
import DonutChart from '../components/charts/DonutChart'
import AIChatPanel from '../components/ai/AIChatPanel'
import { useLeads } from '../hooks/useLeads'
import { useAnalytics } from '../hooks/useAnalytics'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const { stats, reload } = useLeads()
  const { data: analytics, reload: reloadAnalytics } = useAnalytics()
  const navigate = useNavigate()

  const manualReload = async () => {
    try {
      await Promise.all([reload(), reloadAnalytics()])
    } catch {
      // hooks handle errors internally
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
    return funnelData.reduce((sum, s) => sum + s.count, 0)
  }, [funnelData])

  const donutSegments = useMemo(() => {
    return [
      { label: 'Novos', value: stats.novos ?? 0, color: '#ffffff' },
      { label: 'Contatados', value: stats.contatados ?? 0, color: '#888888' },
      { label: 'Fechados', value: stats.fechados ?? 0, color: '#22c55e' },
      { label: 'Perdidos', value: stats.perdidos ?? 0, color: '#dc2626' },
    ]
  }, [stats])

  const donutTotal = useMemo(() => {
    return donutSegments.reduce((sum, s) => sum + s.value, 0)
  }, [donutSegments])

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-4xl font-semibold tracking-tight text-white">
          Nexus Leads Manager
        </h1>
        <p className="mt-2 text-base text-[#666666]">
          Inteligência operacional para geração de oportunidades.
        </p>
      </div>

      <StatsCards
        stats={stats}
        leadsThisMonth={analytics?.leads_this_month ?? 0}
        onFilter={(status) => {
          navigate(`/app/leads?status=${status}`)
        }}
      />

      <div className="grid gap-8 xl:grid-cols-[1fr_400px]">
        <div className="space-y-8">
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

