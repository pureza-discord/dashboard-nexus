interface Stage {
  stage: string
  count: number
}

const stageColors: Record<string, string> = {
  Novos: '#60a5fa',
  Contatados: '#a1a1aa',
  Proposta: '#f59e0b',
  Fechados: '#22c55e',
  Perdidos: '#ef4444',
}

export default function FunnelChart({ data, total }: { data: Stage[]; total: number }) {
  const safeData = data.length
    ? data
    : [
        { stage: 'Novos', count: 0 },
        { stage: 'Contatados', count: 0 },
        { stage: 'Proposta', count: 0 },
        { stage: 'Fechados', count: 0 },
        { stage: 'Perdidos', count: 0 },
      ]

  const max = Math.max(...safeData.map((s) => s.count), 1)
  const safeTotal = Math.max(total, 1)

  return (
    <div className="card p-5 md:p-6">
      <h3 className="mb-5 text-[13px] font-medium text-nexus-muted">Funil de conversao</h3>
      <div className="space-y-3.5">
        {safeData.map((stage) => {
          const pct = ((stage.count / safeTotal) * 100).toFixed(1)
          const width = Math.max((stage.count / max) * 100, stage.count > 0 ? 2 : 0)
          const color = stageColors[stage.stage] || '#a1a1aa'

          return (
            <div key={stage.stage}>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <span className="text-[13px] text-nexus-muted">{stage.stage}</span>
                <span className="text-[13px] font-medium tabular-nums text-white">
                  {stage.count}
                  <span className="ml-1 text-nexus-muted">({pct}%)</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ backgroundColor: color, width: `${width}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
