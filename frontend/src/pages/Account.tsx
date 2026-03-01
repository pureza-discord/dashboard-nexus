import { Coins, LogOut, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'

export default function Account() {
  const { user, logout, reloadUser } = useAuth()

  const subscribe = async (planType: 'basic' | 'pro' | 'enterprise') => {
    await api('/api/billing/subscribe', {
      method: 'POST',
      body: JSON.stringify({ plan_type: planType }),
    })
    await reloadUser()
  }

  const buyCredits = async () => {
    await api('/api/billing/credits/buy', {
      method: 'POST',
      body: JSON.stringify({ amount: 500 }),
    })
    await reloadUser()
  }

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-white">Conta</h1>
        <p className="mt-1 text-sm text-[#666666]">Gerencie seu plano e informações.</p>
      </div>

      <div className="max-w-lg space-y-6">
        <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0a] p-6">
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#555555]">
            Email
          </p>
          <p className="mt-2 text-base font-medium text-white">{user?.email || '-'}</p>
          {user?.full_name ? (
            <>
              <p className="mt-4 text-[11px] font-medium uppercase tracking-[0.12em] text-[#555555]">
                Nome
              </p>
              <p className="mt-2 text-base font-medium text-white">{user.full_name}</p>
            </>
          ) : null}
        </div>

        <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0a] p-6">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[#888888]" />
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#555555]">
              Plano
            </p>
          </div>
          <p className="mt-3 text-lg font-semibold text-white">
            {user?.is_admin ? 'Admin' : (user?.plan_type || 'Gratuito')}
          </p>

          <div className="mt-4 space-y-2 text-[13px] text-[#888888]">
            <p>
              Leads no mês: {user?.billing?.leads_used_current_month ?? 0}
              {user?.is_admin
                ? ' / Ilimitado'
                : user?.billing?.leads_limit_mensal
                  ? ` / ${user.billing.leads_limit_mensal}`
                  : ' / Ilimitado'}
            </p>
            <p>Créditos: {user?.credits_balance ?? 0}</p>
          </div>

          {!user?.is_admin ? (
            <div className="mt-6 space-y-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[#555555]">
                Assinatura
              </p>
              <div className="flex gap-2">
                {(['basic', 'pro', 'enterprise'] as const).map((plan) => (
                  <button
                    key={plan}
                    type="button"
                    onClick={() => { void subscribe(plan) }}
                    className="rounded-lg border border-white/[0.08] px-4 py-2 text-[13px] font-medium capitalize text-[#888888] transition hover:border-white/[0.2] hover:text-white"
                  >
                    {plan}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => { void buyCredits() }}
                className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] px-4 py-2 text-[13px] font-medium text-[#888888] transition hover:border-white/[0.2] hover:text-white"
              >
                <Coins className="h-4 w-4" />
                Comprar +500 créditos
              </button>
            </div>
          ) : null}
        </div>

        <button
          type="button"
          onClick={() => { void logout() }}
          className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] px-4 py-2.5 text-[13px] font-medium text-[#666666] transition hover:border-nexus-red/30 hover:text-nexus-red"
        >
          <LogOut className="h-4 w-4" />
          Sair da conta
        </button>
      </div>
    </div>
  )
}
