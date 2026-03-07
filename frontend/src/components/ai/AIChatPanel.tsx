import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, SendHorizonal } from 'lucide-react'
import { api } from '../../services/api'
import { useAuth } from '../../context/AuthContext'
import { useTheme, THEME_LABELS } from '../../context/ThemeContext'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  task_id?: string | null
  metadata?: Record<string, unknown>
  created_at?: string
}

type AITask = {
  id: string
  task_type: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  requested_quantity: number
  completed_quantity: number
  parsed_payload: Record<string, unknown>
  result_payload: Record<string, unknown>
  error_message?: string | null
}

type ChatResponse = {
  intent: string
  requires_confirmation: boolean
  parsed_request?: Record<string, unknown>
  task?: AITask
  assistant_message?: ChatMessage
  user_message?: ChatMessage
}

interface Props {
  onDataChanged?: () => Promise<void> | void
}

const STATUS_MAP: Record<string, { key: string; label: string }> = {
  novos: { key: 'novos', label: 'Novos' },
  contatados: { key: 'contatados', label: 'Contatados' },
  proposta: { key: 'proposta', label: 'Proposta' },
  fechados: { key: 'fechados', label: 'Fechados' },
  perdidos: { key: 'perdidos', label: 'Perdidos' },
}

const COMMANDS_HELP = `Comandos disponíveis:

/help — Exibe esta lista de comandos
/clear — Limpa todas as mensagens do chat
/novos — Lista leads com status "Novos"
/contatados — Lista leads com status "Contatados"
/proposta — Lista leads com status "Proposta"
/fechados — Lista leads com status "Fechados"
/perdidos — Lista leads com status "Perdidos"
/credits — Mostra seus créditos restantes
/layout — Altera o tema da página inteira (Dark, Light, Dracula)
/pesquisar {Nicho} {UF} {Cidade} {Qtd} — Busca leads
  Ex: /pesquisar Restaurantes SP "São Paulo" 50

Digite qualquer mensagem em linguagem natural para conversar comigo.`

const INTRO_MESSAGE = `Eu sou o Jarvis — Assistente de AI para geração de Leads.
Posso buscar empresas por nicho, cidade ou analisar mercado.

${COMMANDS_HELP}`

export default function AIChatPanel({ onDataChanged }: Props) {
  const { user } = useAuth()
  const { theme, cycleTheme } = useTheme()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [pendingConfirm, setPendingConfirm] = useState<{
    message: string
    parsed: Record<string, unknown>
    intent: string
  } | null>(null)
  const [activeTask, setActiveTask] = useState<AITask | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(true)

  const listRef = useRef<HTMLDivElement | null>(null)

  const loadHistory = async () => {
    const res = await api<{ items: ChatMessage[] }>('/api/ai/messages?limit=80')
    setMessages(res.items || [])
  }

  const loadRecentTask = async () => {
    const res = await api<{ items: AITask[] }>('/api/ai/tasks?limit=1')
    if (res.items && res.items.length > 0) {
      const latest = res.items[0]
      if (latest.status === 'queued' || latest.status === 'running') {
        setActiveTask(latest)
      }
    }
  }

  useEffect(() => {
    let mounted = true
    const boot = async () => {
      try {
        await Promise.all([loadHistory(), loadRecentTask()])
      } finally {
        if (mounted) setLoadingHistory(false)
      }
    }
    void boot()
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, activeTask])

  useEffect(() => {
    if (!activeTask || !['queued', 'running'].includes(activeTask.status)) return
    const id = window.setInterval(async () => {
      try {
        const fresh = await api<AITask>(`/api/ai/tasks/${activeTask.id}`)
        setActiveTask(fresh)
        if (fresh.status === 'completed' || fresh.status === 'failed' || fresh.status === 'cancelled') {
          await loadHistory()
          if (onDataChanged) await onDataChanged()
        }
      } catch {
        // keep polling
      }
    }, 2000)
    return () => window.clearInterval(id)
  }, [activeTask?.id, activeTask?.status, onDataChanged])

  const addLocalMessage = useCallback((role: 'assistant' | 'system', content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}-${Math.random()}`, role, content },
    ])
  }, [])

  const handleCommand = useCallback(async (raw: string): Promise<boolean> => {
    const trimmed = raw.trim()
    if (!trimmed.startsWith('/')) return false

    const parts = trimmed.split(/\s+/)
    const cmd = parts[0].toLowerCase()

    if (cmd === '/clear') {
      try {
        await api('/api/ai/messages', { method: 'DELETE' })
        setMessages([])
        setPendingConfirm(null)
        setActiveTask(null)
      } catch {
        addLocalMessage('assistant', 'Erro ao limpar chat no servidor. Nenhuma mensagem foi removida.')
      }
      return true
    }

    if (cmd === '/help') {
      addLocalMessage('assistant', COMMANDS_HELP)
      return true
    }

    if (cmd === '/credits') {
      const billing = user?.billing
      if (!billing) {
        addLocalMessage('assistant', 'Não foi possível carregar informações de créditos.')
        return true
      }
      const balance = billing.available_credits ?? user?.credits_balance ?? 0
      const resetDate = billing.plan_reset_date
      const leadsLimit = billing.max_leads_per_search
      const leadsUsed = billing.leads_used_current_month

      let msg = `Créditos e limites da sua conta (${billing.plan_display_name}):\n\n`
      msg += `Créditos disponíveis: ${balance}\n`
      if (leadsLimit !== null) {
        msg += `Buscas limitadas a ${leadsLimit} leads por vez\n`
      } else {
        msg += `Buscas ilimitadas por vez\n`
      }
      msg += `Leads processados este mês: ${leadsUsed}\n`
      
      if (billing.days_until_reset) {
        msg += `\nRenova em: ${billing.days_until_reset} dias`
      } else if (resetDate) {
        msg += `\nReset mensal em: ${new Date(resetDate).toLocaleDateString('pt-BR')}`
      } else {
        msg += `\nSeus créditos não expiram.`
      }
      addLocalMessage('assistant', msg)
      return true
    }

    if (cmd === '/layout') {
      const next = cycleTheme()
      addLocalMessage('assistant', `Tema alterado para: ${THEME_LABELS[next]}`)
      return true
    }

    // Status commands: /novos, /contatados, /proposta, /fechados, /perdidos
    const statusCmd = cmd.slice(1)
    if (STATUS_MAP[statusCmd]) {
      const status = STATUS_MAP[statusCmd]
      try {
        const res = await api<{ leads: { id: string; empresa: string; cidade?: string; telefone?: string }[] }>(
          `/api/leads?status=${status.key}&limit=50`
        )
        const items = res.leads || []
        if (items.length === 0) {
          addLocalMessage('assistant', `Nenhum lead encontrado com status "${status.label}".`)
        } else {
          const lines = items.map((l, i) => `${i + 1}. ${l.empresa}${l.cidade ? ` — ${l.cidade}` : ''}${l.telefone ? ` | ${l.telefone}` : ''}`)
          addLocalMessage('assistant', `Leads com status "${status.label}" (${items.length}):\n\n${lines.join('\n')}`)
        }
      } catch {
        addLocalMessage('assistant', `Erro ao buscar leads com status "${status.label}".`)
      }
      return true
    }

    // /pesquisar {Nicho} {UF} {Cidade} {Qtd}
    if (cmd === '/pesquisar') {
      if (parts.length < 5) {
        addLocalMessage('assistant', 'Uso: /pesquisar {Nicho} {UF} {Cidade} {Quantidade}\nEx: /pesquisar Restaurantes SP "São Paulo" 50')
        return true
      }
      // Handle quoted city names in remaining parts
      const remaining = parts.slice(3).join(' ')
      const quoteMatch = remaining.match(/^"([^"]+)"\s+(\d+)/)
      let qtdStr: string
      if (quoteMatch) {
        qtdStr = quoteMatch[2]
      } else {
        qtdStr = parts[4]
      }
      const quantidade = parseInt(qtdStr, 10)
      if (isNaN(quantidade) || quantidade <= 0) {
        addLocalMessage('assistant', 'Quantidade inválida. Use um número positivo.\nEx: /pesquisar Restaurantes SP "São Paulo" 50')
        return true
      }
      // Will be handled in handleSubmit to delegate to sendChat
      return false
    }

    // Unknown command
    addLocalMessage('assistant', `Comando desconhecido: ${cmd}\nDigite /help para ver os comandos disponíveis.`)
    return true
  }, [theme, user, addLocalMessage, cycleTheme])

  const canSend = input.trim().length > 0 && !sending

  const sendChat = async (message: string, confirmExecution: boolean) => {
    setSending(true)
    try {
      const response = await api<ChatResponse>('/api/ai/chat', {
        method: 'POST',
        body: JSON.stringify({ message, confirm_execution: confirmExecution }),
      })
      await loadHistory()
      if (response.requires_confirmation) {
        setPendingConfirm({
          message,
          parsed: response.parsed_request || {},
          intent: response.intent,
        })
      } else {
        setPendingConfirm(null)
        if (confirmExecution) {
          setMessages([])
          await loadHistory()
        }
      }
      if (response.task) {
        setActiveTask(response.task)
      }
      if (response.task && onDataChanged) {
        await onDataChanged()
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Erro ao processar mensagem'
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Erro: ${errorMsg}`,
        },
      ])
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const message = input.trim()
    if (!message || sending) return
    setInput('')

    // Check if it's a /pesquisar command that needs to be transformed
    if (message.toLowerCase().startsWith('/pesquisar')) {
      const parts = message.trim().split(/\s+/)
      if (parts.length >= 5) {
        const nicho = parts[1]
        const uf = parts[2].toUpperCase()
        const remaining = parts.slice(3).join(' ')
        const quoteMatch = remaining.match(/^"([^"]+)"\s+(\d+)/)
        let cidade: string
        let qtdStr: string
        if (quoteMatch) {
          cidade = quoteMatch[1]
          qtdStr = quoteMatch[2]
        } else {
          cidade = parts[3]
          qtdStr = parts[4]
        }
        const quantidade = parseInt(qtdStr, 10)
        if (!isNaN(quantidade) && quantidade > 0) {
          const searchMsg = `Buscar ${quantidade} ${nicho} em ${cidade}, ${uf}`
          void sendChat(searchMsg, false)
          return
        }
      }
    }

    const handled = await handleCommand(message)
    if (!handled) {
      void sendChat(message, false)
    }
  }

  const taskProgress = activeTask?.progress || 0

  const taskLabel = useMemo(() => {
    if (!activeTask) return ''
    if (activeTask.task_type === 'scraping') return 'Busca de leads'
    if (activeTask.task_type === 'market_intelligence') return 'Relatório de mercado'
    return activeTask.task_type
  }, [activeTask])

  return (
    <aside
      className="flex max-h-[calc(100vh-12rem)] min-h-[400px] flex-col overflow-hidden rounded-xl transition-colors duration-300"
      style={{ background: 'var(--t-surface)', border: '1px solid var(--t-border)' }}
    >
      <div className="px-5 py-4" style={{ borderBottom: '1px solid var(--t-border)' }}>
        <p className="text-[13px] font-semibold" style={{ color: 'var(--t-text)' }}>Jarvis</p>
        <p className="mt-0.5 text-[12px]" style={{ color: 'var(--t-muted2)' }}>Assistente de AI para geração de Leads</p>
      </div>

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-5">
        {loadingHistory ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
          </div>
        ) : (
          <>
            <div className="rounded-lg px-4 py-3" style={{ background: 'var(--t-bubble-bot)' }}>
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed" style={{ color: 'var(--t-muted2)' }}>
                {INTRO_MESSAGE}
              </p>
            </div>

            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </>
        )}

        {activeTask ? (
          <div className="rounded-lg p-4" style={{ border: '1px solid var(--t-border)', background: 'var(--t-bubble-bot)' }}>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em]" style={{ color: 'var(--t-muted2)' }}>
              {taskLabel}
            </p>
            <p className="mt-1 text-[13px] font-medium" style={{ color: 'var(--t-text)' }}>
              {activeTask.status === 'completed'
                ? 'Concluída'
                : activeTask.status === 'failed'
                  ? 'Falhou'
                  : 'Em processamento'}
            </p>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div
                className="h-full rounded-full bg-white/40 transition-all duration-500"
                style={{ width: `${taskProgress}%` }}
              />
            </div>
            <p className="mt-2 text-[12px] tabular-nums" style={{ color: 'var(--t-muted2)' }}>{taskProgress}%</p>
          </div>
        ) : null}
      </div>

      {pendingConfirm ? (
        <div className="px-5 py-3" style={{ borderTop: '1px solid var(--t-border)', background: 'var(--t-bubble-bot)' }}>
          <p className="text-[13px] font-medium" style={{ color: 'var(--t-text)' }}>Confirma execução?</p>
          <p className="mt-1 text-[12px]" style={{ color: 'var(--t-muted)' }}>
            {pendingConfirm.intent === 'scrape'
              ? `Nicho: ${String(pendingConfirm.parsed.nicho || '-')}, Cidade: ${String(pendingConfirm.parsed.cidade || '-')}, Quantidade: ${String(pendingConfirm.parsed.quantidade || '-')}`
              : `Nicho: ${String(pendingConfirm.parsed.nicho || '-')}, Cidade: ${String(pendingConfirm.parsed.cidade || '-')}`}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              disabled={sending}
              onClick={() => { void sendChat(pendingConfirm.message, true) }}
              className="rounded-lg border border-nexus-green/20 px-3 py-1.5 text-[13px] font-medium text-nexus-green transition hover:border-nexus-green/40 hover:bg-nexus-green/10"
            >
              Confirmar
            </button>
            <button
              type="button"
              disabled={sending}
              onClick={() => setPendingConfirm(null)}
              className="rounded-lg px-3 py-1.5 text-[13px] font-medium transition hover:opacity-80"
              style={{ border: '1px solid var(--t-border)', color: 'var(--t-muted)' }}
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      <form
        onSubmit={(e) => { void handleSubmit(e) }}
        className="p-4"
        style={{ borderTop: '1px solid var(--t-border)' }}
      >
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSubmit(e as unknown as React.FormEvent)
              }
            }}
            rows={2}
            placeholder="Ex: /pesquisar Clínicas SP Recife 200"
            className="flex-1 resize-none rounded-lg px-3 py-2.5 text-[13px] transition"
            style={{
              border: '1px solid var(--t-input-border)',
              background: 'var(--t-input-bg)',
              color: 'var(--t-text)',
            }}
          />
          <button
            type="submit"
            disabled={!canSend}
            className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg transition hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-30"
            style={{ border: '1px solid var(--t-border)', color: 'var(--t-muted2)' }}
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <SendHorizonal className="h-4 w-4" />}
          </button>
        </div>
      </form>
    </aside>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div
      className={`rounded-lg px-4 py-3 transition-colors hover:brightness-110 ${isUser ? 'ml-6' : 'mr-6'}`}
      style={{ background: isUser ? 'var(--t-bubble-user)' : 'var(--t-bubble-bot)' }}
    >
      <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em]" style={{ color: 'var(--t-muted2)' }}>
        {isUser ? 'Você' : 'Jarvis'}
      </p>
      <p className="whitespace-pre-wrap text-[13px] leading-relaxed" style={{ color: 'var(--t-text)' }}>{message.content}</p>
    </div>
  )
}
