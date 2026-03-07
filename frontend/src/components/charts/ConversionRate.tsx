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
    <div className="card flex flex-col items-center p-5 md:p-6">
      <h3 className="mb-2 text-[13px] font-medium text-nexus-muted">{label}</h3>
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
              <Cell fill="rgba(255,255,255,0.06)" />
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
