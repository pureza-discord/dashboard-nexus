import { useMemo } from 'react'

interface Segment {
  label: string
  value: number
  color: string
}

interface Props {
  segments: Segment[]
  total: number
}

export default function DonutChart({ segments, total }: Props) {
  const safeTotal = Math.max(total, 1)
  const hasData = total > 0

  const size = 200
  const strokeWidth = 22
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const cx = size / 2
  const cy = size / 2

  const arcs = useMemo(() => {
    const gap = 3
    return segments.reduce(
      (acc, segment) => {
        const pct = segment.value / safeTotal
        const length = Math.max(0, pct * circumference)
        const nextArc = {
          ...segment,
          pct,
          length,
          offset: acc.nextOffset,
        }

        return {
          nextOffset: acc.nextOffset + length + gap,
          list: [...acc.list, nextArc],
        }
      },
      { nextOffset: 0, list: [] as Array<Segment & { pct: number; length: number; offset: number }> }
    ).list
  }, [segments, safeTotal, circumference])

  return (
    <div className="card p-5 md:p-6">
      <h3 className="mb-5 text-[13px] font-medium text-nexus-muted">Distribuicao de leads</h3>

      <div className="flex flex-col items-center gap-5 lg:flex-row lg:items-center lg:justify-between lg:gap-8">
        <div className="relative flex-shrink-0">
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
            <circle
              cx={cx}
              cy={cy}
              r={radius}
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth={strokeWidth}
            />
            {arcs.map((arc) => {
              if (!hasData || arc.length <= 0) return null
              return (
                <circle
                  key={arc.label}
                  cx={cx}
                  cy={cy}
                  r={radius}
                  fill="none"
                  stroke={arc.color}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                  strokeDasharray={`${arc.length} ${circumference}`}
                  strokeDashoffset={-arc.offset}
                  style={{ transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
                />
              )
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-semibold tracking-tight text-white">{total}</span>
            <span className="text-[11px] uppercase tracking-widest text-nexus-muted">total</span>
          </div>
        </div>

        <div className="w-full max-w-[240px] space-y-3">
          {arcs.map((arc) => (
            <div key={arc.label} className="flex items-center gap-3">
              <div className="h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ backgroundColor: arc.color }} />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-[12px] text-nexus-muted">{arc.label}</p>
                  <p className="text-[13px] font-medium tabular-nums text-white">
                    {arc.value}
                    <span className="ml-1 text-nexus-muted">({(arc.pct * 100).toFixed(0)}%)</span>
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
