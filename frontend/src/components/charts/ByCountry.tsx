import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface Props {
  data: { country: string; count: number }[]
}

export default function ByCountry({ data }: Props) {
  return (
    <div className="bg-nexus-card border border-white/[0.06] rounded-xl p-5">
      <h3 className="text-sm font-semibold text-zinc-300 mb-4">Leads por pais</h3>
      <ResponsiveContainer width="100%" height={Math.max(120, data.length * 40)}>
        <BarChart data={data} layout="vertical">
          <XAxis type="number" tick={{ fontSize: 10, fill: '#71717a' }} tickLine={false} axisLine={false} />
          <YAxis dataKey="country" type="category" tick={{ fontSize: 11, fill: '#a1a1aa' }} tickLine={false} axisLine={false} width={90} />
          <Tooltip
            contentStyle={{ background: '#18181b', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#a1a1aa' }}
            itemStyle={{ color: '#3b82f6' }}
          />
          <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={20} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
