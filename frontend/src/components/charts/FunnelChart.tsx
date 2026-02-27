interface Stage {
  stage: string
  count: number
  color: string
}

export default function FunnelChart({ data, total }: { data: Stage[]; total: number }) {
  const max = Math.max(...data.map((d) => d.count), 1)

  return (
    <div className="bg-nexus-card border border-white/[0.06] rounded-xl p-5">
      <h3 className="text-sm font-semibold text-zinc-300 mb-4">Funil de conversao</h3>
      <div className="space-y-3">
        {data.map((s) => {
          const pct = total > 0 ? ((s.count / total) * 100).toFixed(1) : '0'
          const barW = max > 0 ? (s.count / max) * 100 : 0
          return (
            <div key={s.stage}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-zinc-400">{s.stage}</span>
                <span className="text-xs font-medium text-zinc-300">{s.count} ({pct}%)</span>
              </div>
              <div className="h-7 bg-zinc-900 rounded-lg overflow-hidden">
                <div
                  className="h-full rounded-lg transition-all duration-700 flex items-center pl-2"
                  style={{ width: `${Math.max(barW, 2)}%`, background: s.color }}
                >
                  {barW > 15 && <span className="text-[10px] font-bold text-white/80">{s.count}</span>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
