import { create } from 'zustand'

export type ChatRole = 'user' | 'assistant' | 'system' | 'tool'

export type ChatMessage = {
  id: string
  chat_id: string
  role: ChatRole
  content: string
  tool_calls?: unknown
  created_at?: string
}

export type Conversation = {
  id: string
  title: string
  awaiting_confirmation?: boolean
  created_at?: string
  updated_at?: string
  messages: ChatMessage[]
}

export type ChatTask = {
  id: string
  chat_id?: string | null
  task_type: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  requested_quantity: number
  completed_quantity: number
  parsed_payload: Record<string, unknown>
  result_payload: Record<string, unknown>
  error_message?: string | null
}

type ChatState = {
  activeConversationId: string | null
  conversations: Record<string, Conversation>
  orderedConversationIds: string[]
  activeTasks: Record<string, ChatTask>
  setConversations: (items: Conversation[]) => void
  upsertConversation: (item: Omit<Conversation, 'messages'> & { messages?: ChatMessage[] }) => void
  setActiveConversationId: (id: string | null) => void
  replaceMessages: (chatId: string, messages: ChatMessage[]) => void
  appendMessages: (chatId: string, messages: ChatMessage[]) => void
  clearConversationMessages: (chatId: string) => void
  setTask: (chatId: string, task: ChatTask | null) => void
  resetStore: () => void
}

function dedupeMessages(messages: ChatMessage[]): ChatMessage[] {
  const byId = new Map<string, ChatMessage>()
  for (const msg of messages) {
    byId.set(msg.id, msg)
  }
  return [...byId.values()].sort((a, b) => {
    const left = a.created_at ? Date.parse(a.created_at) : 0
    const right = b.created_at ? Date.parse(b.created_at) : 0
    return left - right
  })
}

export const useChatStore = create<ChatState>((set) => ({
  activeConversationId: null,
  conversations: {},
  orderedConversationIds: [],
  activeTasks: {},

  setConversations: (items) => {
    const map: Record<string, Conversation> = {}
    const ids: string[] = []

    for (const item of items) {
      map[item.id] = {
        ...item,
        messages: dedupeMessages(item.messages || []),
      }
      ids.push(item.id)
    }

    set((state) => ({
      conversations: map,
      orderedConversationIds: ids,
      activeConversationId: state.activeConversationId && map[state.activeConversationId]
        ? state.activeConversationId
        : ids[0] || null,
    }))
  },

  upsertConversation: (item) => {
    set((state) => {
      const existing = state.conversations[item.id]
      const conversation: Conversation = {
        id: item.id,
        title: item.title,
        awaiting_confirmation: item.awaiting_confirmation,
        created_at: item.created_at,
        updated_at: item.updated_at,
        messages: dedupeMessages(item.messages || existing?.messages || []),
      }

      const ordered = state.orderedConversationIds.includes(item.id)
        ? state.orderedConversationIds
        : [item.id, ...state.orderedConversationIds]

      return {
        conversations: {
          ...state.conversations,
          [item.id]: conversation,
        },
        orderedConversationIds: ordered,
        activeConversationId: state.activeConversationId || item.id,
      }
    })
  },

  setActiveConversationId: (id) => set({ activeConversationId: id }),

  replaceMessages: (chatId, messages) => {
    set((state) => {
      const existing = state.conversations[chatId]
      if (!existing) return state

      return {
        conversations: {
          ...state.conversations,
          [chatId]: {
            ...existing,
            messages: dedupeMessages(messages),
          },
        },
      }
    })
  },

  appendMessages: (chatId, messages) => {
    if (!messages.length) return
    set((state) => {
      const existing = state.conversations[chatId]
      if (!existing) return state

      return {
        conversations: {
          ...state.conversations,
          [chatId]: {
            ...existing,
            messages: dedupeMessages([...existing.messages, ...messages]),
          },
        },
      }
    })
  },

  clearConversationMessages: (chatId) => {
    set((state) => {
      const existing = state.conversations[chatId]
      if (!existing) return state
      return {
        conversations: {
          ...state.conversations,
          [chatId]: {
            ...existing,
            messages: [],
          },
        },
      }
    })
  },

  setTask: (chatId, task) => {
    set((state) => {
      if (!task) {
        const next = { ...state.activeTasks }
        delete next[chatId]
        return { activeTasks: next }
      }
      return {
        activeTasks: {
          ...state.activeTasks,
          [chatId]: task,
        },
      }
    })
  },

  resetStore: () => {
    set({
      activeConversationId: null,
      conversations: {},
      orderedConversationIds: [],
      activeTasks: {},
    })
  },
}))

export function getActiveConversation(): Conversation | null {
  const state = useChatStore.getState()
  const id = state.activeConversationId
  if (!id) return null
  return state.conversations[id] || null
}

export function getConversationMessages(chatId: string): ChatMessage[] {
  const state = useChatStore.getState()
  return state.conversations[chatId]?.messages || []
}

export function getConversationTask(chatId: string): ChatTask | null {
  const state = useChatStore.getState()
  return state.activeTasks[chatId] || null
}
