import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface Props {
  data: { date: string; count: number }[]
}

export default function LeadsPerDay({ data }: Props) {
  const formatted = data.map((d) => ({
    ...d,
    label: d.date.slice(5),
  }))

  return (
    <div className="bg-nexus-card border border-white/[0.06] rounded-xl p-5">
      <h3 className="text-sm font-semibold text-zinc-300 mb-4">Leads por dia (30 dias)</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={formatted}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#71717a' }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#71717a' }} tickLine={false} axisLine={false} width={30} />
          <Tooltip
            contentStyle={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#a1a1aa' }}
            itemStyle={{ color: '#3b82f6' }}
          />
          <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
