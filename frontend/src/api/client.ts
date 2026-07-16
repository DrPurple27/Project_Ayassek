const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData
  const res = await fetch(`${BASE}${path}`, {
    headers: isFormData ? (options?.headers as Record<string, string>) : { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// Unwrap common {status, data} wrapper
async function unwrap<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await request<{ status: string; data: T }>(path, options)
  return res.data
}

export interface RagStatusData {
  enabled: boolean
  vector_count: number
  embedding_model: string
  reranker_enabled: boolean
  reranker_model: string | null
  chunking_strategy: string
}

export interface IngestTaskStatus {
  task_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_stage: string
  current_page: number
  total_pages: number
  result?: {
    chunks_created: number
    vectors_stored: number
    errors?: string[]
  }
  error?: string
  created_at: string
  updated_at: string
}

export interface RagQueryData {
  context: string
  chunks: any[]
  reranked: any[]
  metadata: any
}

export interface ListEntityItem {
  name: string
  category: string
  summary_preview: string
  facts_count: number
}

export interface EntityDetail {
  name: string
  category: string
  summary: string
  facts: BrainFact[]
  path: string
  created_at: string
  updated_at: string
}

export interface BrainFact {
  id: string
  text: string
  category: string
  tags: string[]
  timestamp: string
  status: string
  source: string
  importance: number
  version_history: { text: string; status: string; timestamp: string }[]
}

export interface SearchResult {
  entity: string
  category: string
  fact_id: string
  text: string
  tags: string[]
  timestamp: string
  score: number
}

export interface SessionItem {
  id: string
  name: string
  summary: string
  created_at: number
  updated_at: number
}

export const api = {
  chat: (body: { message: string; session_id?: string }) =>
    request<{ status: string; session_id: string }>('/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getSessions: () =>
    request<{ sessions: SessionItem[] }>('/chat/sessions'),

  createSession: (name?: string) =>
    request<{ session_id: string; name: string }>('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ name: name || 'New Session' }),
    }),

  deleteSession: (sessionId: string) =>
    request<{ status: string; session_id: string }>(`/chat/sessions/${sessionId}`, {
      method: 'DELETE',
    }),

  renameSession: (sessionId: string, name: string) =>
    request<{ status: string; session_id: string; name: string }>(`/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    }),

  getSessionMessages: (sessionId: string, limit?: number) =>
    request<{ session_id: string; messages: any[] }>(`/chat/sessions/${sessionId}/messages${limit ? `?limit=${limit}` : ''}`),

  clearSession: (sessionId: string) =>
    request<{ status: string; session_id: string }>('/chat/session/clear', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    }),

  // Providers
  getProviders: () =>
    request<{ providers: any[]; active_provider: string; active_model: string }>('/providers'),

  // Backend: GET /api/providers/models?provider_id=X
  getModels: (providerId: string) =>
    request<{ provider_id: string; models: any[] }>(`/providers/models?provider_id=${providerId}`),

  // Backend: POST /api/providers/select {provider_id, model}
  setActiveProvider: (providerId: string, model?: string) =>
    request<{ status: string; provider: string; model?: string }>('/providers/select', {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId, model: model || '' }),
    }),

  // RAG — responses wrapped in {status, data} or {status, ...fields}
  ragQuery: (body: { query: string; top_k?: number; rerank?: boolean; category?: string }) =>
    request<{ status: string; context: string; chunks: any[]; reranked: any[]; metadata: any }>('/rag/query', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  ragStatus: () =>
    unwrap<RagStatusData>('/rag/status'),

  ragIngest: (body: { text: string; source: string; category?: string; tags?: string[] }) =>
    request<{ status: string; chunks_created: number; vectors_stored: number }>('/rag/ingest', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // DELETE /api/rag/source/{source} — soft delete by source path
  ragDeleteSource: (source: string) =>
    request<{ status: string; deleted: number }>(`/rag/source/${encodeURIComponent(source)}`, {
      method: 'DELETE',
    }),

  // POST /api/rag/ingest/file — upload and queue file
  ragIngestFile: (file: File, category?: string, tags?: string[]) => {
    const form = new FormData()
    form.append('file', file)
    if (category) form.append('category', category)
    if (tags) form.append('tags', tags.join(','))
    return request<{ status: string; task_id: string }>('/rag/ingest/file', {
      method: 'POST',
      body: form,
    })
  },

  // GET /api/rag/ingest/status/{task_id} — check ingestion task status
  ragIngestStatus: (taskId: string) =>
    request<{ status: string; data: IngestTaskStatus }>(`/rag/ingest/status/${taskId}`),

  // DELETE /api/rag/category/{category} — soft delete by category
  ragDeleteCategory: (category: string) =>
    request<{ status: string; deleted: number }>(`/rag/category/${encodeURIComponent(category)}`, {
      method: 'DELETE',
    }),

  ragReindex: () =>
    request<{ status: string }>('/rag/reindex', { method: 'POST' }),

  // Second Brain — all list/detail wrapped in {status, data}
  brainEntities: (category?: string) =>
    unwrap<ListEntityItem[]>(`/brain/entities${category ? `?category=${category}` : ''}`),

  // GET /api/brain/entities/{category}/{name} returns entity with embedded facts
  brainEntity: (category: string, name: string) =>
    unwrap<EntityDetail>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}`),

  brainCreateEntity: (body: { name: string; category: string; summary?: string }) =>
    unwrap<EntityDetail>('/brain/entities', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // POST /api/brain/search with body {query, category?, top_k}
  brainSearch: (body: { query: string; category?: string; top_k?: number }) =>
    unwrap<any[]>('/brain/search', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  brainStats: () =>
    unwrap<{ total_entities: number; total_active_facts: number }>('/brain/stats'),

  // PUT /api/brain/entities/{category}/{name} — update summary
  brainUpdateEntity: (category: string, name: string, summary: string) =>
    request<{ status: string }>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify({ summary }),
    }),

  // DELETE /api/brain/entities/{category}/{name} — soft delete
  brainDeleteEntity: (category: string, name: string) =>
    request<{ status: string; deleted: boolean }>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  // PUT /api/brain/entities/{category}/{name}/position — update x,y
  brainUpdateEntityPosition: (category: string, name: string, x: number, y: number) =>
    request<{ status: string }>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}/position`, {
      method: 'PUT',
      body: JSON.stringify({ x, y }),
    }),

  // POST /api/brain/entities/{category}/{name}/facts — add fact
  brainAddFact: (category: string, name: string, body: { text: string; tags?: string[]; status?: string; source?: string; importance?: number }) =>
    request<{ status: string; fact_id: string }>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}/facts`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // PUT /api/brain/entities/{category}/{name}/facts/{fact_id} — update fact
  brainUpdateFact: (category: string, name: string, factId: string, body: { text?: string; status?: string; tags?: string[]; importance?: number }) =>
    request<{ status: string }>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}/facts/${encodeURIComponent(factId)}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  // DELETE /api/brain/entities/{category}/{name}/facts/{fact_id} — soft delete
  brainDeleteFact: (category: string, name: string, factId: string) =>
    request<{ status: string; deleted: boolean }>(`/brain/entities/${encodeURIComponent(category)}/${encodeURIComponent(name)}/facts/${encodeURIComponent(factId)}`, {
      method: 'DELETE',
    }),

  // POST /api/brain/index — index to vectors
  brainIndexVectors: () =>
    request<{ status: string; indexed: number }>('/brain/index', { method: 'POST' }),

  // System
  getStatus: () =>
    request<{ uptime: number; system: any; resources: any; ayassek: any }>('/system/status'),

  getReady: () =>
    request<{ ready: boolean; steps: any[] }>('/system/ready'),

  // Voice settings
  getVoiceSettings: () =>
    request<{ stt: any; tts: any; stt_available: boolean; tts_available: boolean }>('/voice/settings'),

  updateVoiceSettings: (body: { stt?: Record<string, any>; tts?: Record<string, any> }) =>
    request<{ status: string }>('/voice/settings', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Voice transcription
  transcribeVoice: (formData: FormData) =>
    request<{ text: string; language: string; segments: any[]; duration: number }>('/voice/transcribe', {
      method: 'POST',
      body: formData,
      headers: {}, // Let browser set Content-Type for FormData
    }),

  // Unified NRS Graph
  fetchGraph: () =>
    request<{ status: string; nodes: any[]; edges: any[] }>('/brain/graph'),

  createNeuron: (title: string, content: string, x?: number, y?: number) =>
    request<any>('/memory/nodes', {
      method: 'POST',
      body: JSON.stringify({ title, content, x, y }),
    }),

  updateNeuron: (id: string, fields: any) =>
    request<any>(`/memory/nodes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(fields),
    }),

  deleteNeuron: (id: string) =>
    request<{ status: string }>(`/memory/nodes/${id}`, { method: 'DELETE' }),

  createSynapse: (sourceId: string, targetId: string, strength?: number) =>
    request<any>('/memory/edges', {
      method: 'POST',
      body: JSON.stringify({ source_id: sourceId, target_id: targetId, strength: strength || 1 }),
    }),

  deleteSynapse: (id: string) =>
    request<{ status: string }>(`/memory/edges/${id}`, { method: 'DELETE' }),

  brainReset: () =>
    request<{ status: string; details: any }>('/brain/reset', { method: 'POST' }),

  ragWipe: () =>
    request<{ status: string }>('/rag/wipe', { method: 'POST' }),
}
