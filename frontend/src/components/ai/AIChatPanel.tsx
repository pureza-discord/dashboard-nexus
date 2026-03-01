import { useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, SendHorizonal } from 'lucide-react'
import { api } from '../../services/api'

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

const INTRO_MESSAGE = `Eu sou o Nexus Leads Manager.
Inteligência comercial para identificar oportunidades reais.
Posso buscar empresas por nicho, cidade ou analisar mercado.
Como posso te ajudar hoje?`

export default function AIChatPanel({ onDataChanged }: Props) {
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
      }
      if (response.task) {
        setActiveTask(response.task)
      }
      if (response.task && onDataChanged) {
        await onDataChanged()
      }
    } finally {
      setSending(false)
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
    <aside className="flex min-h-[600px] flex-col overflow-hidden rounded-xl border border-white/[0.06] bg-[#0a0a0a]">
      <div className="border-b border-white/[0.06] px-5 py-4">
        <p className="text-[13px] font-semibold text-white">Nexus Leads Manager</p>
        <p className="mt-0.5 text-[12px] text-[#555555]">Assistente de inteligência comercial</p>
      </div>

      <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-5">
        {loadingHistory ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
          </div>
        ) : (
          <>
            <div className="rounded-lg bg-white/[0.03] px-4 py-3">
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-[#999999]">
                {INTRO_MESSAGE}
              </p>
            </div>

            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </>
        )}

        {activeTask ? (
          <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-[#666666]">
              {taskLabel}
            </p>
            <p className="mt-1 text-[13px] font-medium text-white">
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
            <p className="mt-2 text-[12px] tabular-nums text-[#555555]">{taskProgress}%</p>
          </div>
        ) : null}
      </div>

      {pendingConfirm ? (
        <div className="border-t border-white/[0.06] bg-white/[0.02] px-5 py-3">
          <p className="text-[13px] font-medium text-white">Confirma execução?</p>
          <p className="mt-1 text-[12px] text-[#888888]">
            {pendingConfirm.intent === 'scrape'
              ? `Nicho: ${String(pendingConfirm.parsed.nicho || '-')}, Cidade: ${String(pendingConfirm.parsed.cidade || '-')}, Quantidade: ${String(pendingConfirm.parsed.quantidade || '-')}`
              : `Nicho: ${String(pendingConfirm.parsed.nicho || '-')}, Cidade: ${String(pendingConfirm.parsed.cidade || '-')}`}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              disabled={sending}
              onClick={() => { void sendChat(pendingConfirm.message, true) }}
              className="rounded-lg border border-nexus-green/20 px-3 py-1.5 text-[13px] font-medium text-nexus-green transition hover:border-nexus-green/40"
            >
              Confirmar
            </button>
            <button
              type="button"
              disabled={sending}
              onClick={() => setPendingConfirm(null)}
              className="rounded-lg border border-white/[0.08] px-3 py-1.5 text-[13px] font-medium text-[#888888] transition hover:border-white/[0.15]"
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          const message = input.trim()
          if (!message || sending) return
          setInput('')
          void sendChat(message, false)
        }}
        className="border-t border-white/[0.06] p-4"
      >
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={2}
            placeholder="Ex: Buscar 200 clínicas em Recife..."
            className="flex-1 resize-none rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2.5 text-[13px] text-white placeholder-[#444444] transition focus:border-white/[0.15]"
          />
          <button
            type="submit"
            disabled={!canSend}
            className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-white/[0.08] text-[#888888] transition hover:border-white/[0.2] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
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
      className={`rounded-lg px-4 py-3 ${
        isUser
          ? 'ml-6 bg-white/[0.06]'
          : 'mr-6 bg-white/[0.03]'
      }`}
    >
      <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-[#555555]">
        {isUser ? 'Você' : 'Nexus Leads Manager'}
      </p>
      <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-white">{message.content}</p>
    </div>
  )
}
