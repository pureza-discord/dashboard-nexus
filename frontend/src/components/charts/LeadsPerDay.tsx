import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Props {
  data: { date: string; count: number }[]
}

export default function LeadsPerDay({ data }: Props) {
  const formatted = data.map((point) => ({
    ...point,
    label: point.date.slice(5),
  }))

  return (
    <div className="rounded-2xl border border-white/10 bg-nexus-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-zinc-300">Leads por dia (ultimos 30 dias)</h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={formatted}>
          <defs>
            <linearGradient id="leadsGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="4 4" stroke="rgba(255,255,255,0.06)" />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#71717a' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#71717a' }} tickLine={false} axisLine={false} width={30} />
          <Tooltip
            contentStyle={{
              background: '#131623',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 10,
              fontSize: 12,
            }}
            labelStyle={{ color: '#a1a1aa' }}
            itemStyle={{ color: '#93c5fd' }}
          />
          <Area type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2.2} fill="url(#leadsGradient)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
