import { create } from 'zustand'
import { api } from '@/api/client'

export interface NRSEntityNode {
  id: string
  type: 'entity' | 'fact' | 'neuron'
  title: string
  category?: string
  summary?: string
  content?: string
  status?: string
  facts_count?: number
  source: 'second_brain' | 'graph_db'
  x?: number | null
  y?: number | null
}

export interface NRSEdge {
  id: string
  source: string
  target: string
  strength?: number
  is_manual?: boolean
  label?: string
}

interface NRSState {
  nodes: NRSEntityNode[]
  edges: NRSEdge[]
  selectedNodeId: string | null
  loading: boolean
  error: string | null

  fetchGraph: () => Promise<void>
  selectNode: (id: string | null) => void
  createEntity: (category: string, name: string, summary?: string) => Promise<void>
  deleteEntity: (category: string, name: string) => Promise<void>
  createNeuron: (title: string, content?: string, x?: number, y?: number) => Promise<void>
  updateNeuron: (id: string, fields: Partial<NRSEntityNode>) => Promise<void>
  deleteNeuron: (id: string) => Promise<void>
  createEdge: (sourceId: string, targetId: string, strength?: number) => Promise<void>
  deleteEdge: (edgeId: string) => Promise<void>
  resetAll: () => Promise<void>

  // Optimistic actions for real-time updates
  addEntityOptimistic: (entity: Omit<NRSEntityNode, 'id' | 'source'> & { id: string }) => void
  addFactOptimistic: (entityId: string, fact: { id: string; title: string; category: string; status?: string }) => void
  addNeuronOptimistic: (neuron: Omit<NRSEntityNode, 'id' | 'source'> & { id: string }) => void
  updateEntityOptimistic: (id: string, fields: Partial<NRSEntityNode>) => void
  removeEntityOptimistic: (id: string) => void
}

export const useNRSStore = create<NRSState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  loading: false,
  error: null,

  selectNode: (id) => set({ selectedNodeId: id }),

  fetchGraph: async () => {
    set({ loading: true, error: null })
    try {
      const res = await api.fetchGraph()
      set({ nodes: res.nodes || [], edges: res.edges || [], loading: false })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      set({ error: msg, loading: false })
      throw e
    }
  },

  createEntity: async (category, name, summary) => {
    try {
      await api.brainCreateEntity({ category, name, summary: summary || '' })
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  deleteEntity: async (category, name) => {
    try {
      await api.brainDeleteEntity(category, name)
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  createNeuron: async (title, content, x, y) => {
    try {
      await api.createNeuron(title, content || '', x, y)
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  updateNeuron: async (id, fields) => {
    try {
      const neuronId = id.replace('neuron:', '')
      await api.updateNeuron(neuronId, fields)
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  deleteNeuron: async (id) => {
    try {
      const neuronId = id.replace('neuron:', '')
      await api.deleteNeuron(neuronId)
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  createEdge: async (sourceId, targetId, strength = 1) => {
    try {
      const rawSource = sourceId.replace('neuron:', '')
      const rawTarget = targetId.replace('neuron:', '')
      await api.createSynapse(rawSource, rawTarget, strength)
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  deleteEdge: async (edgeId) => {
    try {
      const rawId = edgeId.replace('synapse:', '')
      await api.deleteSynapse(rawId)
      await get().fetchGraph()
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '' })
    }
  },

  resetAll: async () => {
    set({ loading: true, error: null })
    try {
      await api.brainReset()
      set({ nodes: [], edges: [], selectedNodeId: null, loading: false })
    } catch (e: unknown) {
      set({ error: e instanceof Error ? e.message : '', loading: false })
    }
  },

  addEntityOptimistic: (entity) => set((state) => {
    if (state.nodes.some((n) => n.id === entity.id)) return state
    return { nodes: [...state.nodes, { ...entity, source: 'second_brain' }] }
  }),

  addFactOptimistic: (entityId, fact) => set((state) => {
    const entity = state.nodes.find((n) => n.id === entityId)
    if (!entity) return state
    return {
      nodes: state.nodes.map((n) =>
        n.id === entityId ? { ...n, facts_count: (n.facts_count || 0) + 1 } : n
      ),
    }
  }),

  addNeuronOptimistic: (neuron) => set((state) => {
    if (state.nodes.some((n) => n.id === neuron.id)) return state
    return { nodes: [...state.nodes, { ...neuron, source: 'graph_db' }] }
  }),

  updateEntityOptimistic: (id, fields) => set((state) => ({
    nodes: state.nodes.map((n) => (n.id === id ? { ...n, ...fields } : n)),
  })),

  removeEntityOptimistic: (id) => set((state) => ({
    nodes: state.nodes.filter((n) => n.id !== id),
    edges: state.edges.filter((e) => e.source !== id && e.target !== id),
  })),
}))
