import { create } from 'zustand'
import { api, type SessionItem } from '@/api/client'

interface ToolCall {
  name: string
  args: string
  result?: string
  status: 'running' | 'complete' | 'error'
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  images?: string[]
  tool_calls?: ToolCall[]
  isStreaming?: boolean
}

interface ChatState {
  messages: ChatMessage[]
  sessionId: string | null
  sessions: SessionItem[]
  isStreaming: boolean
  streamingContent: string
  streamingToolCalls: ToolCall[]
  addMessage: (msg: ChatMessage) => void
  setStreamingContent: (content: string) => void
  addToolCall: (call: ToolCall) => void
  updateToolCall: (name: string, result: string, status: 'complete' | 'error') => void
  addAssistantResponse: (content: string) => void
  setSessionId: (id: string) => void
  setStreaming: (v: boolean) => void
  clear: () => void
  fetchSessions: () => Promise<void>
  createSession: (name?: string) => Promise<string>
  deleteSession: (sessionId: string) => Promise<void>
  renameSession: (sessionId: string, name: string) => Promise<void>
  switchSession: (sessionId: string) => Promise<void>
  updateMessage: (index: number, content: string) => void
  exportMarkdown: () => string
  exportJSON: () => string
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  sessionId: null,
  sessions: [],
  isStreaming: false,
  streamingContent: '',
  streamingToolCalls: [],

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  setStreamingContent: (content) =>
    set({ streamingContent: content }),

  addToolCall: (call) =>
    set((s) => ({ streamingToolCalls: [...s.streamingToolCalls, call] })),

  updateToolCall: (name, result, status) =>
    set((s) => ({
      streamingToolCalls: s.streamingToolCalls.map((tc) =>
        tc.name === name ? { ...tc, result, status } : tc
      ),
    })),

  addAssistantResponse: (content) =>
    set((s) => {
      const hasStreaming = s.messages.some((m) => m.isStreaming)
      if (hasStreaming) {
        return {
          messages: s.messages.map((m) =>
            m.isStreaming
              ? { ...m, content: m.content + content, isStreaming: false, tool_calls: s.streamingToolCalls }
              : m
          ),
          isStreaming: false,
          streamingContent: '',
          streamingToolCalls: [],
        }
      }
      return {
        messages: [
          ...s.messages,
          {
            role: 'assistant',
            content,
            timestamp: Date.now(),
            tool_calls: s.streamingToolCalls.length > 0 ? s.streamingToolCalls : undefined,
          },
        ],
        isStreaming: false,
        streamingContent: '',
        streamingToolCalls: [],
      }
    }),

  setSessionId: (id) => set({ sessionId: id }),
  setStreaming: (v) => set({ isStreaming: v }),
  clear: () => set({ messages: [], sessionId: null, streamingContent: '', streamingToolCalls: [] }),

  fetchSessions: async () => {
    try {
      const res = await api.getSessions()
      set({ sessions: res.sessions || [] })
    } catch (e: unknown) {
      console.warn('Failed to fetch sessions', e instanceof Error ? e.message : e)
    }
  },

  createSession: async (name?: string) => {
    const res = await api.createSession(name)
    const item: SessionItem = { id: res.session_id, name: res.name, summary: '', created_at: Date.now() / 1000, updated_at: Date.now() / 1000 }
    set((s) => ({ sessions: [item, ...s.sessions], sessionId: res.session_id, messages: [] }))
    return res.session_id
  },

  deleteSession: async (sessionId: string) => {
    await api.deleteSession(sessionId)
    set((s) => {
      const sessions = s.sessions.filter((x) => x.id !== sessionId)
      const newSessionId = s.sessionId === sessionId ? (sessions[0]?.id ?? null) : s.sessionId
      return { sessions, sessionId: newSessionId, messages: s.sessionId === sessionId ? [] : s.messages }
    })
  },

  renameSession: async (sessionId: string, name: string) => {
    await api.renameSession(sessionId, name)
    set((s) => ({
      sessions: s.sessions.map((x) => (x.id === sessionId ? { ...x, name } : x)),
    }))
  },

  switchSession: async (sessionId: string) => {
    set({ sessionId, messages: [], streamingContent: '', streamingToolCalls: [] })
    try {
      const res = await api.getSessionMessages(sessionId)
      const msgs: ChatMessage[] = (res.messages || []).map((m: any) => ({
        role: m.role,
        content: m.content,
        timestamp: (m.created_at || 0) * 1000,
      }))
      set({ messages: msgs })
    } catch (e: unknown) {
      console.warn('Failed to load session messages', e instanceof Error ? e.message : e)
    }
  },

  updateMessage: (index, content) =>
    set((s) => ({
      messages: s.messages.map((m, i) => (i === index ? { ...m, content } : m)),
    })),

  exportMarkdown: () => {
    const { messages } = get()
    return messages
      .map((m) => `**${m.role === 'user' ? 'You' : 'Assistant'}** (${new Date(m.timestamp).toLocaleString()})\n\n${m.content}`)
      .join('\n\n---\n\n')
  },

  exportJSON: () => {
    const { messages } = get()
    return JSON.stringify(messages.map(({ isStreaming: _isStreaming, ...rest }) => rest), null, 2)
  },
}))
