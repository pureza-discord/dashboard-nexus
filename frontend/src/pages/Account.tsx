import { Coins, LogOut, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'

export default function Account() {
  const { user, logout, reloadUser } = useAuth()

  const subscribe = async (planType: 'free' | 'go' | 'pro' | 'plus' | 'ilimitado') => {
    // Calling the admin plan change endpoint just as a mock for UI
    await api('/api/billing/admin/plan', {
      method: 'POST',
      body: JSON.stringify({ user_id: user?.id, plan_type: planType }),
    })
    await reloadUser()
  }

  const buyCredits = async () => {
    // Calling the admin credit adjustment endpoint just as a mock for UI
    await api('/api/billing/admin/credits', {
      method: 'POST',
      body: JSON.stringify({ user_id: user?.id, amount: 500, description: "UI mockup purchase" }),
    })
    await reloadUser()
  }

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight" style={{ color: 'var(--t-text)' }}>Conta</h1>
        <p className="mt-1 text-sm" style={{ color: 'var(--t-muted4)' }}>Gerencie seu plano e informações.</p>
      </div>

      <div className="max-w-lg space-y-6">
        <div
          className="rounded-xl p-6 transition-colors duration-300"
          style={{ background: 'var(--t-surface)', border: '1px solid var(--t-border)' }}
        >
          <p className="text-[11px] font-medium uppercase tracking-[0.12em]" style={{ color: 'var(--t-muted5)' }}>
            Email
          </p>
          <p className="mt-2 text-base font-medium" style={{ color: 'var(--t-text)' }}>{user?.email || '-'}</p>
          {user?.full_name ? (
            <>
              <p className="mt-4 text-[11px] font-medium uppercase tracking-[0.12em]" style={{ color: 'var(--t-muted5)' }}>
                Nome
              </p>
              <p className="mt-2 text-base font-medium" style={{ color: 'var(--t-text)' }}>{user.full_name}</p>
            </>
          ) : null}
        </div>

        <div
          className="rounded-xl p-6 transition-colors duration-300"
          style={{ background: 'var(--t-surface)', border: '1px solid var(--t-border)' }}
        >
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" style={{ color: 'var(--t-muted)' }} />
            <p className="text-[11px] font-medium uppercase tracking-[0.12em]" style={{ color: 'var(--t-muted5)' }}>
              Plano
            </p>
          </div>
          <p className="mt-3 text-lg font-semibold" style={{ color: 'var(--t-text)' }}>
            {user?.billing?.is_admin ? 'Admin' : (user?.billing?.plan_display_name || 'Gratuito')}
          </p>

          <div className="mt-4 space-y-2 text-[13px]" style={{ color: 'var(--t-muted)' }}>
            <p>Créditos disponíveis: {user?.billing?.available_credits ?? 0}</p>
            {user?.billing?.days_until_reset ? (
              <p>Renova em: {user.billing.days_until_reset} dias</p>
            ) : null}
            <p>Limite de busca: {user?.billing?.max_leads_per_search || 'Ilimitado'} leads</p>
          </div>

          {!user?.is_admin ? (
            <div className="mt-6 space-y-3">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em]" style={{ color: 'var(--t-muted5)' }}>
                Assinatura
              </p>
              <div className="flex flex-wrap gap-2">
                {(['go', 'pro', 'plus', 'ilimitado'] as const).map((plan) => (
                  <button
                    key={plan}
                    type="button"
                    onClick={() => { void subscribe(plan) }}
                    className="rounded-lg px-4 py-2 text-[13px] font-medium capitalize transition hover:opacity-80"
                    style={{ border: '1px solid var(--t-input-border)', color: 'var(--t-muted)' }}
                  >
                    {plan}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => { void buyCredits() }}
                className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-medium transition hover:opacity-80"
                style={{ border: '1px solid var(--t-input-border)', color: 'var(--t-muted)' }}
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
          className="inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-[13px] font-medium transition hover:border-nexus-red/30 hover:text-nexus-red"
          style={{ border: '1px solid var(--t-input-border)', color: 'var(--t-muted4)' }}
        >
          <LogOut className="h-4 w-4" />
          Sair da conta
        </button>
      </div>
    </div>
  )
}
