import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'

interface Props {
  rate: number
  label: string
  color: string
}

export default function ConversionRate({ rate, label, color }: Props) {
  const data = [
    { value: rate },
    { value: 100 - rate },
  ]

  return (
    <div className="bg-nexus-card border border-white/[0.06] rounded-xl p-5 flex flex-col items-center">
      <h3 className="text-sm font-semibold text-zinc-300 mb-2">{label}</h3>
      <div className="relative w-32 h-32">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              innerRadius={42}
              outerRadius={56}
              startAngle={90}
              endAngle={-270}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={color} />
              <Cell fill="#27272a" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-bold text-white">{rate}%</span>
        </div>
      </div>
    </div>
  )
}
