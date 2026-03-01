interface Stage {
  stage: string
  count: number
}

const stageColors: Record<string, string> = {
  Novos: '#ffffff',
  Contatados: '#888888',
  Proposta: '#666666',
  Fechados: '#22c55e',
  Perdidos: '#dc2626',
}

export default function FunnelChart({ data, total }: { data: Stage[]; total: number }) {
  if (total === 0) return null

  const max = Math.max(...data.map((s) => s.count), 1)

  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0a] p-6">
      <h3 className="mb-6 text-sm font-medium text-[#888888]">Funil de conversão</h3>
      <div className="space-y-4">
        {data.map((stage) => {
          const pct = total > 0 ? ((stage.count / total) * 100).toFixed(1) : '0'
          const width = max > 0 ? (stage.count / max) * 100 : 0
          const color = stageColors[stage.stage] || '#666666'

          return (
            <div key={stage.stage}>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[13px] text-[#999999]">{stage.stage}</span>
                <span className="text-[13px] font-medium text-white tabular-nums">
                  {stage.count}
                  <span className="ml-1 text-[#555555]">({pct}%)</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/[0.04]">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${Math.max(width, 1)}%`,
                    backgroundColor: color,
                    opacity: 0.7,
                  }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
