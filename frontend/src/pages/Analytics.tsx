import { Loader2, DollarSign, TrendingUp, Users, Target } from 'lucide-react'
import Header from '../components/layout/Header'
import LeadsPerDay from '../components/charts/LeadsPerDay'
import FunnelChart from '../components/charts/FunnelChart'
import ConversionRate from '../components/charts/ConversionRate'
import ByCountry from '../components/charts/ByCountry'
import { useAnalytics } from '../hooks/useAnalytics'
import { formatCurrency } from '../utils/format'

function MetricCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: string; color: string }) {
  return (
    <div className="bg-nexus-card border border-white/[0.06] rounded-xl p-5">
      <div className="flex items-center gap-3 mb-2">
        <div className={`w-8 h-8 rounded-lg ${color} flex items-center justify-center`}>
          <Icon className="w-4 h-4 text-white" />
        </div>
        <span className="text-xs text-zinc-500 uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  )
}

export default function Analytics() {
  const { data, loading } = useAnalytics()

  if (loading || !data) {
    return (
      <>
        <Header title="Analytics" />
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 text-nexus-accent animate-spin" />
        </div>
      </>
    )
  }

  return (
    <>
      <Header title="Analytics" />
      <main className="p-6 space-y-6">
        {/* Top metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard icon={Users} label="Total de leads" value={String(data.total)} color="bg-zinc-700" />
          <MetricCard icon={Target} label="Taxa de contato" value={`${data.contact_rate}%`} color="bg-amber-600" />
          <MetricCard icon={TrendingUp} label="Taxa de conversao" value={`${data.conversion_rate}%`} color="bg-blue-600" />
          <MetricCard icon={DollarSign} label="Receita estimada" value={formatCurrency(data.estimated_revenue)} color="bg-emerald-600" />
        </div>

        {/* Charts row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <LeadsPerDay data={data.leads_per_day} />
          </div>
          <FunnelChart data={data.funnel} total={data.total} />
        </div>

        {/* Charts row 2 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <ConversionRate rate={data.conversion_rate} label="Conversao (fechados)" color="#3b82f6" />
          <ConversionRate rate={data.contact_rate} label="Contato (contatados)" color="#f59e0b" />
          <ByCountry data={data.by_country} />
        </div>
      </main>
    </>
  )
}
