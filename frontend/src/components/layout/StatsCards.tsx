import { cn } from '../../lib/utils'

interface Props {
  stats: Record<string, number>
  leadsThisMonth: number
  onFilter: (status: string) => void
}

const cards = [
  { key: '_month', label: 'Leads este mes', valueKey: 'month' },
  { key: 'novos', label: 'Novos', valueKey: 'novos' },
  { key: 'contatados', label: 'Contatados', valueKey: 'contatados' },
  { key: 'fechados', label: 'Fechados', valueKey: 'fechados', positive: true },
  { key: 'perdidos', label: 'Perdidos', valueKey: 'perdidos', negative: true },
]

export default function StatsCards({ stats, leadsThisMonth, onFilter }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
      {cards.map(({ key, label, valueKey, positive, negative }) => {
        const value = valueKey === 'month' ? leadsThisMonth : (stats[valueKey] ?? 0)
        const isClickable = key !== '_month'

        return (
          <button
            key={key}
            type="button"
            disabled={!isClickable}
            onClick={() => { if (isClickable) onFilter(key) }}
            className={cn(
              'card group px-4 py-4 text-left',
              isClickable && 'cursor-pointer hover:border-white/[0.15]',
              !isClickable && 'cursor-default',
            )}
          >
            <p className="text-[11px] font-medium uppercase tracking-wider text-nexus-muted">{label}</p>
            <p
              className={cn(
                'mt-2 text-3xl font-semibold leading-none tracking-tight',
                positive && 'text-emerald-400',
                negative && 'text-red-400',
                !positive && !negative && 'text-white',
              )}
            >
              {value}
            </p>
          </button>
        )
      })}
    </div>
  )
}
