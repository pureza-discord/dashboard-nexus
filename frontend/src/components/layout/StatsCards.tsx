interface Props {
  stats: Record<string, number>
  leadsThisMonth: number
  onFilter: (status: string) => void
}

const cards = [
  { key: '_month', label: 'Leads este mês', valueKey: 'month' },
  { key: 'novos', label: 'Novos', valueKey: 'novos' },
  { key: 'contatados', label: 'Contatados', valueKey: 'contatados' },
  { key: 'fechados', label: 'Fechados', valueKey: 'fechados', positive: true },
  { key: 'perdidos', label: 'Perdidos', valueKey: 'perdidos', negative: true },
]

export default function StatsCards({ stats, leadsThisMonth, onFilter }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map(({ key, label, valueKey, positive, negative }) => {
        const value = valueKey === 'month' ? leadsThisMonth : (stats[valueKey] ?? 0)
        const isClickable = key !== '_month'

        return (
          <button
            key={key}
            type="button"
            disabled={!isClickable}
            onClick={() => {
              if (isClickable) onFilter(key)
            }}
            className={`group rounded-xl border border-white/[0.06] bg-[#0a0a0a] p-5 text-left transition-colors ${
              isClickable ? 'cursor-pointer hover:border-white/[0.12]' : 'cursor-default'
            }`}
          >
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#666666]">
              {label}
            </p>
            <p
              className={`mt-3 text-3xl font-semibold tracking-tight ${
                positive
                  ? 'text-nexus-green'
                  : negative
                    ? 'text-nexus-red'
                    : 'text-white'
              }`}
            >
              {value}
            </p>
          </button>
        )
      })}
    </div>
  )
}

