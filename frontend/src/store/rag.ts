import { create } from 'zustand'
import { api, type RagStatusData, type IngestTaskStatus } from '@/api/client'

interface RagState {
  status: RagStatusData | null
  queryResult: { context: string; chunks: any[]; reranked: any[] } | null
  ingestTask: IngestTaskStatus | null
  loading: boolean
  error: string | null
  fetchStatus: () => Promise<void>
  query: (q: string, rerank?: boolean) => Promise<void>
  ingest: (text: string, source: string) => Promise<void>
  ingestFile: (file: File, category?: string, tags?: string[]) => Promise<string>
  pollTask: (taskId: string) => Promise<void>
  deleteSource: (source: string) => Promise<void>
  deleteCategory: (category: string) => Promise<void>
  wipeAll: () => Promise<void>
}

export const useRagStore = create<RagState>((set, get) => ({
  status: null,
  queryResult: null,
  ingestTask: null,
  loading: false,
  error: null,

  fetchStatus: async () => {
    set({ loading: true, error: null })
    try {
      const status = await api.ragStatus()
      set({ status, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  query: async (q, rerank) => {
    set({ loading: true, error: null })
    try {
      const res = await api.ragQuery({ query: q, rerank })
      set({ queryResult: { context: res.context, chunks: res.chunks, reranked: res.reranked }, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  ingest: async (text, source) => {
    set({ loading: true, error: null })
    try {
      await api.ragIngest({ text, source })
      set({ loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  ingestFile: async (file, category, tags) => {
    set({ loading: true, error: null })
    try {
      const res = await api.ragIngestFile(file, category, tags)
      set({ loading: false })
      return res.task_id
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
      throw e
    }
  },

  pollTask: async (taskId) => {
    let done = false
    while (!done) {
      try {
        const res = await api.ragIngestStatus(taskId)
        const task = res.data
        set({ ingestTask: task })
        if (task.status === 'completed' || task.status === 'failed') {
          done = true
          get().fetchStatus()
        }
      } catch (e: unknown) {
        set({ error: e instanceof Error ? e.message : '' })
        done = true
      }
      if (!done) await new Promise(r => setTimeout(r, 1000))
    }
  },

  deleteSource: async (source) => {
    set({ loading: true, error: null })
    try {
      await api.ragDeleteSource(source)
      set({ loading: false })
      get().fetchStatus()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  deleteCategory: async (category) => {
    set({ loading: true, error: null })
    try {
      await api.ragDeleteCategory(category)
      set({ loading: false })
      get().fetchStatus()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  wipeAll: async () => {
    set({ loading: true, error: null })
    try {
      await api.ragWipe()
      set({ status: null, queryResult: null, ingestTask: null, loading: false })
      get().fetchStatus()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },
}))
