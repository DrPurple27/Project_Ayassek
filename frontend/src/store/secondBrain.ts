import { create } from 'zustand'
import { api, type ListEntityItem, type EntityDetail, type BrainFact, type SearchResult } from '@/api/client'

const SEMANTIC_TAGS = [
  'Técnicas', 'Pessoas', 'Projeto', 'Emoção', 'Local', 'Tempo', 'Prioridade',
] as const

function computeImportance(fact: { text: string; tags: string[]; source: string }): number {
  let score = 50
  const text = fact.text.toLowerCase()

  if (fact.tags.includes('Prioridade')) score += 30
  if (fact.tags.includes('Emoção')) score += 15
  if (fact.tags.includes('Projeto')) score += 20
  if (fact.tags.includes('Pessoas')) score += 10
  if (fact.source === 'chat' || fact.source === 'user') score += 10
  if (text.length > 100) score += 5

  return Math.min(100, Math.max(0, score))
}

interface SecondBrainState {
  entities: ListEntityItem[]
  selectedEntity: EntityDetail | null
  facts: BrainFact[]
  searchResults: SearchResult[]
  stats: { total_entities: number; total_active_facts: number } | null
  loading: boolean
  error: string | null

  fetchEntities: (category?: string) => Promise<void>
  selectEntity: (entity: ListEntityItem) => Promise<void>
  clearSelection: () => void

  createEntity: (name: string, category: string, summary?: string) => Promise<void>
  updateEntitySummary: (category: string, name: string, summary: string) => Promise<void>
  deleteEntity: (category: string, name: string) => Promise<void>

  addFact: (category: string, name: string, text: string, tags?: string[]) => Promise<void>
  updateFact: (category: string, name: string, factId: string, body: { text?: string; status?: string; tags?: string[] }) => Promise<void>
  deleteFact: (category: string, name: string, factId: string) => Promise<void>

  search: (query: string, category?: string) => Promise<void>
  clearSearch: () => void
  fetchStats: () => Promise<void>
  indexToVectors: () => Promise<void>
}

export const useSecondBrainStore = create<SecondBrainState>((set, _get) => ({
  entities: [],
  selectedEntity: null,
  facts: [],
  searchResults: [],
  stats: null,
  loading: false,
  error: null,

  fetchEntities: async (category) => {
    set({ loading: true, error: null })
    try {
      const entities = await api.brainEntities(category)
      set({ entities, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  selectEntity: async (entity) => {
    set({ loading: true, error: null, searchResults: [] })
    try {
      const detail = await api.brainEntity(entity.category, entity.name)
      set({ selectedEntity: detail, facts: detail.facts, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', selectedEntity: null, facts: [], loading: false })
    }
  },

  clearSelection: () => set({ selectedEntity: null, facts: [] }),

  createEntity: async (name, category, summary) => {
    set({ loading: true, error: null })
    try {
      await api.brainCreateEntity({ name, category, summary })
      const entities = await api.brainEntities()
      set({ entities, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  updateEntitySummary: async (category, name, summary) => {
    set({ loading: true, error: null })
    try {
      await api.brainUpdateEntity(category, name, summary)
      const detail = await api.brainEntity(category, name)
      set({ selectedEntity: detail, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  deleteEntity: async (category, name) => {
    set({ loading: true, error: null })
    try {
      await api.brainDeleteEntity(category, name)
      const entities = await api.brainEntities()
      set({ entities, selectedEntity: null, facts: [], loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  addFact: async (category, name, text, tags) => {
    set({ loading: true, error: null })
    try {
      const importance = computeImportance({ text, tags: tags ?? [], source: 'manual' })
      const body: any = { text, tags, status: 'active', source: 'manual' }
      if (importance > 0) body.importance = importance

      await api.brainAddFact(category, name, body)
      const detail = await api.brainEntity(category, name)
      set({ selectedEntity: detail, facts: detail.facts, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  updateFact: async (category, name, factId, body) => {
    set({ loading: true, error: null })
    try {
      await api.brainUpdateFact(category, name, factId, body)
      const detail = await api.brainEntity(category, name)
      set({ selectedEntity: detail, facts: detail.facts, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  deleteFact: async (category, name, factId) => {
    set({ loading: true, error: null })
    try {
      await api.brainDeleteFact(category, name, factId)
      const detail = await api.brainEntity(category, name)
      set({ selectedEntity: detail, facts: detail.facts, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  search: async (query, category) => {
    if (!query.trim()) {
      set({ searchResults: [] })
      return
    }
    set({ loading: true, error: null })
    try {
      const results = await api.brainSearch({ query, category, top_k: 20 })
      set({ searchResults: results, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  clearSearch: () => set({ searchResults: [] }),

  fetchStats: async () => {
    try {
      const stats = await api.brainStats()
      set({ stats })
    } catch (_e) {
      // silent
    }
  },

  indexToVectors: async () => {
    set({ loading: true, error: null })
    try {
      await api.brainIndexVectors()
      set({ loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },
}))

export { SEMANTIC_TAGS, computeImportance }
