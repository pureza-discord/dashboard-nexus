import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Props {
  data: { country: string; count: number }[]
}

export default function ByCountry({ data }: Props) {
  return (
    <div className="card p-5 md:p-6">
      <h3 className="mb-4 text-[13px] font-medium text-nexus-muted">Leads por pais</h3>
      <ResponsiveContainer width="100%" height={Math.max(140, data.length * 42)}>
        <BarChart data={data} layout="vertical">
          <XAxis type="number" tick={{ fontSize: 10, fill: '#71717a' }} tickLine={false} axisLine={false} />
          <YAxis
            dataKey="country"
            type="category"
            tick={{ fontSize: 11, fill: '#a1a1aa' }}
            tickLine={false}
            axisLine={false}
            width={90}
          />
          <Tooltip
            contentStyle={{
              background: '#111318',
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: '#a1a1aa' }}
            itemStyle={{ color: '#60a5fa' }}
          />
          <Bar dataKey="count" fill="#60a5fa" radius={[0, 6, 6, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
