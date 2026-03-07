import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronLeft,
  Loader2,
  MessageSquare,
  Plus,
  SendHorizonal,
  Trash2,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'
import {
  type ChatMessage,
  type ChatTask,
  useChatStore,
} from '../../stores/chatStore'

type ChatResponse = {
  intent: string
  requires_confirmation: boolean
  parsed_request?: Record<string, unknown>
  task?: ChatTask
  assistant_message?: ChatMessage
  user_message?: ChatMessage
  chat?: {
    id: string
    title: string
    awaiting_confirmation?: boolean
    created_at?: string
    updated_at?: string
  }
}

interface Props {
  onDataChanged?: () => Promise<void> | void
}

const COMMANDS_TEXT = [
  'Comandos disponiveis:',
  '',
  '/help - Exibe esta lista de comandos',
  '/clear - Limpa todas as mensagens do chat',
  '/novos - Lista leads com status "Novos"',
  '/contatados - Lista leads com status "Contatados"',
  '/proposta - Lista leads com status "Proposta"',
  '/fechados - Lista leads com status "Fechados"',
  '/perdidos - Lista leads com status "Perdidos"',
  '/credits - Mostra seus creditos restantes',
  '/layout - Altera o tema (Light, Dark, Dracula)',
  '/pesquisar {UF} {cidade} {Qtd} - Busca leads',
  'Ex: /pesquisar SP "Sao Paulo" 50',
].join('\n')

const INTRO_MESSAGE = [
  'Eu sou o Jarvis - Assistente de AI para geracao de Leads.',
  'Posso buscar empresas por nicho, cidade ou analisar mercado.',
  '',
  COMMANDS_TEXT,
  '',
  'Digite qualquer mensagem em linguagem natural para conversar comigo.',
].join('\n')

function nowIso() {
  return new Date().toISOString()
}

function tokenizeCommand(value: string): string[] {
  const tokens: string[] = []
  const regex = /"([^"]*)"|'([^']*)'|(\S+)/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(value)) !== null) {
    tokens.push(match[1] || match[2] || match[3])
  }
  return tokens
}

export default function AIChatPanel({ onDataChanged }: Props) {
  const navigate = useNavigate()

  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [input, setInput] = useState('')
  const [pendingConfirm, setPendingConfirm] = useState<{ intent: string; parsed: Record<string, unknown> } | null>(null)
  const [confirmingClear, setConfirmingClear] = useState(false)

  const {
    activeConversationId,
    conversations,
    orderedConversationIds,
    activeTasks,
    setConversations,
    upsertConversation,
    setActiveConversationId,
    replaceMessages,
    appendMessages,
    clearConversationMessages,
    setTask,
  } = useChatStore()

  const messagesRef = useRef<HTMLDivElement | null>(null)
  const loadVersionRef = useRef(0)

  const activeConversation = useMemo(() => {
    if (!activeConversationId) return null
    return conversations[activeConversationId] || null
  }, [activeConversationId, conversations])

  const activeMessages = useMemo(() => activeConversation?.messages || [], [activeConversation])
  const activeTask = activeConversationId ? activeTasks[activeConversationId] || null : null

  const appendLocalAssistant = useCallback((content: string) => {
    if (!activeConversationId) return
    appendMessages(activeConversationId, [
      {
        id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        chat_id: activeConversationId,
        role: 'assistant',
        content,
        created_at: nowIso(),
      },
    ])
  }, [activeConversationId, appendMessages])

  const loadMessages = useCallback(async (chatId: string) => {
    const version = ++loadVersionRef.current
    const response = await api<{ items: ChatMessage[] }>(`/api/ai/chats/${chatId}/messages?limit=120`)
    // Discard stale response if user switched conversations while loading
    if (loadVersionRef.current !== version) return
    replaceMessages(chatId, response.items || [])
  }, [replaceMessages])

  const ensureChat = useCallback(async (): Promise<string> => {
    const chats = await api<{ items: Array<{ id: string; title: string; awaiting_confirmation?: boolean; created_at?: string; updated_at?: string }> }>('/api/ai/chats?limit=100')

    if (!chats.items || chats.items.length === 0) {
      const created = await api<{ id: string; title: string; awaiting_confirmation?: boolean; created_at?: string; updated_at?: string }>('/api/ai/chats', {
        method: 'POST',
        body: JSON.stringify({ title: 'Nova conversa' }),
      })
      upsertConversation({ ...created, messages: [] })
      setActiveConversationId(created.id)
      return created.id
    }

    setConversations(chats.items.map((chat) => ({ ...chat, messages: [] })))

    const current = activeConversationId && chats.items.some((c) => c.id === activeConversationId)
      ? activeConversationId
      : chats.items[0].id

    setActiveConversationId(current)
    return current
  }, [activeConversationId, setActiveConversationId, setConversations, upsertConversation])

  const boot = useCallback(async () => {
    setLoading(true)
    try {
      const chatId = await ensureChat()
      await loadMessages(chatId)
    } finally {
      setLoading(false)
    }
  }, [ensureChat, loadMessages])

  useEffect(() => {
    void boot()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Load messages when switching conversations (not on initial boot)
  const prevConversationRef = useRef<string | null>(null)
  useEffect(() => {
    if (!activeConversationId) return
    // Skip if this is the initial load (boot already loaded messages)
    if (prevConversationRef.current === null) {
      prevConversationRef.current = activeConversationId
      return
    }
    // Only load if conversation actually changed
    if (prevConversationRef.current === activeConversationId) return
    prevConversationRef.current = activeConversationId
    setPendingConfirm(null)
    setConfirmingClear(false)
    void loadMessages(activeConversationId)
  }, [activeConversationId, loadMessages])

  useEffect(() => {
    if (!messagesRef.current) return
    messagesRef.current.scrollTop = messagesRef.current.scrollHeight
  }, [activeMessages, activeTask, pendingConfirm])

  useEffect(() => {
    if (!activeConversationId || !activeTask || !['queued', 'running'].includes(activeTask.status)) return

    const timer = window.setInterval(async () => {
      try {
        const fresh = await api<ChatTask>(`/api/ai/tasks/${activeTask.id}`)
        setTask(activeConversationId, fresh)
        if (fresh.status === 'completed' || fresh.status === 'failed' || fresh.status === 'cancelled') {
          await loadMessages(activeConversationId)
          if (onDataChanged) await onDataChanged()
          window.setTimeout(() => setTask(activeConversationId, null), 1500)
        }
      } catch {
        // keep polling
      }
    }, 2000)

    return () => window.clearInterval(timer)
  }, [activeConversationId, activeTask, loadMessages, onDataChanged, setTask])

  const startNewConversation = useCallback(async () => {
    const created = await api<{ id: string; title: string; awaiting_confirmation?: boolean; created_at?: string; updated_at?: string }>('/api/ai/chats', {
      method: 'POST',
      body: JSON.stringify({ title: 'Nova conversa' }),
    })
    upsertConversation({ ...created, messages: [] })
    // Bump version so any in-flight message loads are discarded
    loadVersionRef.current++
    prevConversationRef.current = created.id
    setActiveConversationId(created.id)
    setPendingConfirm(null)
    setConfirmingClear(false)
    setShowHistory(false)
  }, [setActiveConversationId, upsertConversation])

  const clearHistory = useCallback(async () => {
    if (!activeConversationId) return
    try {
      await api(`/api/ai/chats/${activeConversationId}/messages`, { method: 'DELETE' })
      clearConversationMessages(activeConversationId)
      setPendingConfirm(null)
    } catch {
      // If delete fails on backend, don't clear local state
    }
    setConfirmingClear(false)
  }, [activeConversationId, clearConversationMessages])

  const sendChat = useCallback(async (message: string, confirmExecution: boolean) => {
    if (!activeConversationId) return

    setSending(true)
    try {
      const response = await api<ChatResponse>('/api/ai/chat', {
        method: 'POST',
        body: JSON.stringify({
          chat_id: activeConversationId,
          message,
          confirm_execution: confirmExecution,
        }),
      })

      if (response.chat) {
        upsertConversation({ ...response.chat })
      }

      await loadMessages(activeConversationId)

      if (response.requires_confirmation) {
        setPendingConfirm({
          intent: response.intent,
          parsed: response.parsed_request || {},
        })
      } else {
        setPendingConfirm(null)
      }

      if (response.task) {
        setTask(activeConversationId, response.task)
      }

      if (response.task && onDataChanged) {
        await onDataChanged()
      }
    } finally {
      setSending(false)
    }
  }, [activeConversationId, loadMessages, onDataChanged, setTask, upsertConversation])

  const executeCommand = useCallback(async (rawText: string) => {
    const text = rawText.trim()
    if (!text.startsWith('/')) return false

    const tokens = tokenizeCommand(text)
    if (tokens.length === 0) return true

    const command = tokens[0].toLowerCase()

    if (command === '/help') {
      appendLocalAssistant(COMMANDS_TEXT)
      return true
    }

    if (command === '/clear') {
      await clearHistory()
      appendLocalAssistant('JARVIS\nChat limpo.')
      return true
    }

    if (['/novos', '/contatados', '/proposta', '/fechados', '/perdidos'].includes(command)) {
      const status = command.replace('/', '')
      navigate(`/app/leads?status=${status}`)
      appendLocalAssistant(`Abrindo leads com status "${status}".`)
      return true
    }

    if (command === '/credits') {
      const me = await api<{ billing?: { available_leads?: number | string | null; external_queries_limit_mensal?: number | null; external_queries_used_current_month?: number }; credits_balance?: number }>('/api/auth/me')
      const availableLeads = me.billing?.available_leads ?? 'ilimitado'
      const externalLimit = me.billing?.external_queries_limit_mensal ?? 0
      const externalUsed = me.billing?.external_queries_used_current_month ?? 0
      const creditsBalance = me.credits_balance ?? 0
      appendLocalAssistant(
        `Creditos e limites:\n- Creditos: ${creditsBalance}\n- Leads disponiveis: ${availableLeads}\n- Consultas externas: ${externalUsed}/${externalLimit}`
      )
      return true
    }

    if (command === '/layout') {
      const choice = (tokens[1] || '').toLowerCase()
      const allowed: Record<string, string> = {
        light: 'light',
        dark: 'dark',
        dracula: 'dracula',
      }
      if (!choice || !allowed[choice]) {
        appendLocalAssistant('Uso: /layout Light | Dark | Dracula')
        return true
      }
      const selected = allowed[choice]
      document.documentElement.setAttribute('data-layout', selected)
      window.localStorage.setItem('nexus_layout', selected)
      appendLocalAssistant(`Tema ${selected} aplicado.`)
      return true
    }

    if (command === '/pesquisar') {
      if (tokens.length < 4) {
        appendLocalAssistant('Uso: /pesquisar {UF} {cidade} {Qtd}. Ex: /pesquisar SP "Sao Paulo" 50')
        return true
      }

      const uf = String(tokens[1] || '').toUpperCase()
      const quantity = Number(tokens[tokens.length - 1])
      const cityTokens = tokens.slice(2, -1)
      const city = cityTokens.join(' ').trim()

      if (!/^[A-Z]{2}$/.test(uf)) {
        appendLocalAssistant('UF invalida. Use duas letras, por exemplo: SP')
        return true
      }
      if (!city) {
        appendLocalAssistant('Cidade obrigatoria no comando /pesquisar.')
        return true
      }
      if (!Number.isFinite(quantity) || quantity < 1 || quantity > 100) {
        appendLocalAssistant('Quantidade invalida. Use um numero entre 1 e 100.')
        return true
      }

      const prompt = `busque ${Math.trunc(quantity)} empresas de negocios locais em ${city}, ${uf}, Brasil`
      await sendChat(prompt, false)
      return true
    }

    appendLocalAssistant('Comando nao reconhecido. Use /help para ver os comandos.')
    return true
  }, [appendLocalAssistant, clearHistory, navigate, sendChat])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending || !activeConversationId) return
    setInput('')

    const handled = await executeCommand(text)
    if (!handled) {
      await sendChat(text, false)
    }
  }

  if (showHistory) {
    return (
      <aside className="card flex min-h-[560px] flex-col overflow-hidden">
        <div className="flex items-center gap-3 border-b border-white/[0.06] px-5 py-4">
          <button
            type="button"
            onClick={() => setShowHistory(false)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-nexus-muted transition-colors hover:text-white"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <p className="text-[13px] font-semibold text-white">Conversas</p>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3">
          <div className="space-y-1">
            {orderedConversationIds.map((id) => {
              const chat = conversations[id]
              if (!chat) return null
              return (
                <button
                  key={chat.id}
                  type="button"
                  onClick={() => {
                    loadVersionRef.current++
                    setActiveConversationId(chat.id)
                    setPendingConfirm(null)
                    setConfirmingClear(false)
                    setShowHistory(false)
                  }}
                  className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                    activeConversationId === chat.id
                      ? 'bg-white/[0.08] text-white'
                      : 'text-zinc-400 hover:bg-white/[0.04] hover:text-white'
                  }`}
                >
                  <p className="truncate text-[13px] font-medium">{chat.title}</p>
                  <p className="mt-0.5 text-[11px] text-zinc-600">{chat.messages.length} msgs</p>
                </button>
              )
            })}
          </div>
        </div>
      </aside>
    )
  }

  return (
    <aside className="card flex min-h-[560px] flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3 md:px-5 md:py-4">
        <div>
          <p className="text-[14px] font-semibold text-white">Jarvis</p>
          <p className="mt-0.5 text-[12px] text-nexus-muted">Assistente de AI para geracao de Leads</p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setShowHistory(true)}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-nexus-muted transition-colors hover:bg-white/[0.06] hover:text-white"
            title="Conversas"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => { void startNewConversation() }}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-nexus-muted transition-colors hover:bg-white/[0.06] hover:text-white"
            title="Nova conversa"
          >
            <Plus className="h-4 w-4" />
          </button>
          {confirmingClear ? (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => { void clearHistory() }}
                className="rounded-md px-2 py-1 text-[11px] font-medium text-red-400 transition-colors hover:bg-red-500/15"
                title="Confirmar"
              >
                Limpar
              </button>
              <button
                type="button"
                onClick={() => setConfirmingClear(false)}
                className="rounded-md px-2 py-1 text-[11px] font-medium text-nexus-muted transition-colors hover:bg-white/[0.06]"
                title="Cancelar"
              >
                Nao
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmingClear(true)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-nexus-muted transition-colors hover:bg-white/[0.06] hover:text-white"
              title="Limpar historico"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div ref={messagesRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3 md:px-4 md:py-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-4 w-4 animate-spin text-nexus-muted" />
          </div>
        ) : (
          <>
            {activeMessages.length === 0 ? (
              <MessageBubble
                message={{
                  id: 'intro',
                  chat_id: activeConversationId || 'none',
                  role: 'assistant',
                  content: INTRO_MESSAGE,
                }}
              />
            ) : null}

            {activeMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </>
        )}

        {activeTask ? (
          <div className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-3">
            <p className="text-[11px] font-medium uppercase tracking-wider text-nexus-muted">{activeTask.task_type}</p>
            <p className="mt-1 text-[13px] text-zinc-300">
              {activeTask.status === 'completed' ? 'Concluida' : activeTask.status === 'failed' ? 'Falhou' : 'Processando'}
            </p>
            <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[0.06]">
              <div className="h-full rounded-full bg-white/60 transition-all duration-300" style={{ width: `${activeTask.progress}%` }} />
            </div>
            <p className="mt-2 text-[12px] text-nexus-muted">{activeTask.progress}%</p>
          </div>
        ) : null}
      </div>

      {pendingConfirm ? (
        <div className="border-t border-white/[0.06] bg-white/[0.03] px-4 py-3 md:px-5">
          <p className="text-[13px] font-medium text-white">Confirma execucao?</p>
          <p className="mt-1 text-[12px] text-nexus-muted">
            {Object.entries(pendingConfirm.parsed)
              .filter(([key]) => key !== 'action' && key !== 'original_prompt')
              .map(([key, value]) => `${key}: ${String(value ?? '-')}`)
              .join(' · ')}
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              disabled={sending}
              onClick={() => { void sendChat('Confirmar', true) }}
              className="rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-4 py-1.5 text-[13px] font-medium text-emerald-400 transition-colors hover:bg-emerald-500/25"
            >
              Confirmar
            </button>
            <button
              type="button"
              disabled={sending}
              onClick={() => { void sendChat('Cancelar', false) }}
              className="rounded-lg border border-white/[0.08] px-4 py-1.5 text-[13px] font-medium text-nexus-muted transition-colors hover:border-white/[0.15] hover:text-white"
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      <form onSubmit={(e) => { void handleSubmit(e) }} className="border-t border-white/[0.06] p-3 md:p-4">
        <div className="flex items-end gap-2 md:gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, 2000))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void handleSubmit(e as unknown as React.FormEvent)
              }
            }}
            rows={1}
            placeholder="Ex: /pesquisar SP Recife 200 ou texto livre..."
            className="input-base max-h-40 flex-1 resize-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || sending}
            className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-white/[0.08] text-nexus-muted transition-colors hover:border-white/[0.15] hover:text-white disabled:cursor-not-allowed disabled:opacity-20"
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
      className={`rounded-lg border px-3.5 py-3 md:px-4 ${
        isUser
          ? 'ml-6 rounded-tr-sm border-white/[0.08] bg-white/[0.06] md:ml-8'
          : 'mr-6 rounded-tl-sm border-white/[0.06] bg-white/[0.03] md:mr-8'
      }`}
    >
      <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-nexus-muted">
        {isUser ? 'VOCE' : 'JARVIS'}
      </p>
      <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-zinc-300">{message.content}</p>
    </div>
  )
}
