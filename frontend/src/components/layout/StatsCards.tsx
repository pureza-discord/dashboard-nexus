import { Users, UserPlus, PhoneCall, Trophy } from 'lucide-react'

interface Props {
  stats: Record<string, number>
  onFilter: (status: string) => void
}

const cards = [
  { key: 'total', label: 'Total', icon: Users, color: 'text-zinc-300', bg: 'from-zinc-500/10' },
  { key: 'novo', label: 'Novos', icon: UserPlus, color: 'text-emerald-400', bg: 'from-emerald-500/10' },
  { key: 'contatado', label: 'Contatados', icon: PhoneCall, color: 'text-amber-400', bg: 'from-amber-500/10' },
  { key: 'fechado', label: 'Fechados', icon: Trophy, color: 'text-blue-400', bg: 'from-blue-500/10' },
]

export default function StatsCards({ stats, onFilter }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map(({ key, label, icon: Icon, color, bg }) => (
        <button
          key={key}
          onClick={() => onFilter(key === 'total' ? 'todos' : key)}
          className={`bg-gradient-to-br ${bg} to-transparent bg-nexus-card border border-white/[0.06] rounded-xl p-5 text-left hover:border-white/[0.12] transition-all group`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{label}</span>
            <Icon className={`w-4 h-4 ${color} opacity-60 group-hover:opacity-100 transition`} />
          </div>
          <p className={`text-3xl font-bold ${color}`}>{stats[key] ?? 0}</p>
        </button>
      ))}
    </div>
  )
}
