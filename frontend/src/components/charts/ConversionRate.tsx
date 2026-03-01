import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'

interface Props {
  rate: number
  label: string
  color: string
}

export default function ConversionRate({ rate, label, color }: Props) {
  const capped = Math.max(0, Math.min(rate, 100))
  const data = [{ value: capped }, { value: 100 - capped }]

  return (
    <div className="flex flex-col items-center rounded-2xl border border-white/10 bg-nexus-card p-5">
      <h3 className="mb-2 text-sm font-semibold text-zinc-300">{label}</h3>
      <div className="relative h-36 w-36">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              innerRadius={48}
              outerRadius={62}
              startAngle={90}
              endAngle={-270}
              stroke="none"
            >
              <Cell fill={color} />
              <Cell fill="#272a36" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-semibold text-white">{capped.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  )
}
