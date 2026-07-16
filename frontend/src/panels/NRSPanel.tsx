import { useEffect, useCallback, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  ReactFlowProvider,
  useNodesState,
  useEdgesState,
  MarkerType,
  SelectionMode,
  type Connection,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Brain, Plus, Search, X, ChevronRight, LayoutIcon, Trash2, WifiOff, RotateCcw } from 'lucide-react'
import { useNRSStore } from '@/store/nrs'
import { api } from '@/api/client'
import { useNRSRealtime } from '@/hooks/useNRSRealtime'
import EntityNode from '@/components/graph/EntityNode'
import FactNode from '@/components/graph/FactNode'
import type { EntityDetail, SearchResult } from '@/api/client'
import { graphlib, layout as dagreLayout } from '@dagrejs/dagre'

function layoutDagre(nodes: Node[], edges: Edge[]): Node[] {
  const g = new graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 80, edgesep: 20, marginx: 20, marginy: 20 })
  nodes.forEach(n => g.setNode(n.id, { width: 180, height: n.type === 'fact' ? 100 : 80 }))
  edges.forEach(e => g.setEdge(e.source, e.target))
  dagreLayout(g)
  return nodes.map(n => {
    const pos = g.node(n.id)
    return pos ? { ...n, position: { x: pos.x - 90, y: pos.y - 40 } } : n
  })
}

const NODE_TYPES = {
  entity: EntityNode,
  fact: FactNode,
  neuron: EntityNode,
}

const CATEGORY_COLORS: Record<string, string> = {
  person: '#00f0ff',
  organization: '#8C52FF',
  concept: '#ffaa00',
  event: '#ff2d7b',
  location: '#00ff88',
  project: '#a76bff',
  technology: '#00f0ff',
  default: '#5a5a7a',
}

function NRSPanelInner() {
  const store = useNRSStore()
  useNRSRealtime()
  const [nrsUnavailable, setNrsUnavailable] = useState(false)
  const [initialLoadComplete, setInitialLoadComplete] = useState(false)
  const [errorType, setErrorType] = useState<'none' | 'nrs_missing' | 'connection'>('none')

  // Graph state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [layouting, setLayouting] = useState(false)
  const reactFlowInstance = useReactFlow()

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [activeCategory, setActiveCategory] = useState('')

  // Detail panel state
  const [detailEntity, setDetailEntity] = useState<EntityDetail | null>(null)

  // Create dialog state
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [createMode, setCreateMode] = useState<'entity' | 'neuron'>('entity')
  const [createTitle, setCreateTitle] = useState('')
  const [createCategory, setCreateCategory] = useState('concept')

  // Editing
  const [editingNode, setEditingNode] = useState<Node | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')

  // Fact editor
  const [showFactEditor, setShowFactEditor] = useState(false)
  const [newFactText, setNewFactText] = useState('')
  const [newFactTags, setNewFactTags] = useState<string[]>([])

  // Initial load effect - wait for data before rendering ReactFlow
  useEffect(() => {
    let mounted = true
    const fetchData = async () => {
      try {
        await store.fetchGraph()
        if (mounted) {
          setNrsUnavailable(false)
          setErrorType('none')
          setInitialLoadComplete(true)
        }
      } catch (e) {
        if (mounted) {
          const msg = e instanceof Error ? e.message : ''
          if (msg.includes('NRS') || msg.includes('model') || msg.includes('provider')) {
            setErrorType('nrs_missing')
            setNrsUnavailable(true)
          } else {
            setErrorType('connection')
            setNrsUnavailable(false)
          }
          setInitialLoadComplete(true)
        }
      }
    }
    fetchData()
    return () => { mounted = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fit view after initial load and when nodes change
  const fitViewOnLoad = useCallback(() => {
    if (initialLoadComplete && nodes.length > 0) {
      reactFlowInstance.fitView({ duration: 300 })
    }
  }, [initialLoadComplete, nodes.length, reactFlowInstance])

  useEffect(() => {
    fitViewOnLoad()
  }, [fitViewOnLoad])

  // Entity list derived from graph data
  const entityList = (() => {
    const brainNodes = store.nodes.filter((n) => n.source === 'second_brain' && n.type === 'entity')
    return brainNodes.map((n) => ({
      name: n.title,
      category: n.category || '',
      summary_preview: n.summary || '',
      facts_count: n.facts_count || 0,
    }))
  })()

  useEffect(() => {
    const flowNodes: Node[] = store.nodes.map((n) => ({
      id: n.id,
      type: n.type as 'entity' | 'fact' | 'neuron',
      position: { x: n.x ?? Math.random() * 400, y: n.y ?? Math.random() * 300 },
      data: {
        label: n.title,
        summary: n.summary || n.content?.slice(0, 100),
        category: n.category,
        type: n.type,
        status: n.status,
        source: n.source,
        facts_count: n.facts_count,
      },
    }))
    const flowEdges: Edge[] = store.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label || (e.strength && e.strength > 1 ? String(e.strength) : undefined),
      animated: true,
      style: {
        stroke: e.is_manual ? '#8C52FF' : '#2a2a40',
        strokeWidth: Math.min(3, Math.max(1, e.strength || 1)),
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: e.is_manual ? '#8C52FF' : '#2a2a40' },
    }))
    setNodes(flowNodes)
    setEdges(flowEdges)
  }, [store.nodes, store.edges, setNodes, setEdges])

  const handleAutoLayout = useCallback(() => {
    setLayouting(true)
    const positioned = layoutDagre(nodes, edges)
    setNodes(positioned)
    for (const n of positioned) {
      if (n.id.startsWith('neuron:')) {
        store.updateNeuron(n.id, { x: n.position.x, y: n.position.y })
      } else if (n.id.startsWith('entity:')) {
        const parts = n.id.split(':')
        const cat = parts[1]
        const name = parts.slice(2).join(':')
        api.brainUpdateEntityPosition(cat, name, n.position.x, n.position.y).catch(() => {})
      }
    }
    setLayouting(false)
  }, [nodes, edges, setNodes, store])

  const handleConnect = useCallback(
    async (connection: Connection) => {
      if (connection.source && connection.target) {
        await store.createEdge(connection.source, connection.target)
      }
    },
    [store]
  )

  const handleNodeDragStop = useCallback(
    (_evt: unknown, node: Node) => {
      if (node.id.startsWith('neuron:')) {
        store.updateNeuron(node.id, { x: node.position.x, y: node.position.y })
      } else if (node.id.startsWith('entity:')) {
        const parts = node.id.split(':')
        const cat = parts[1]
        const name = parts.slice(2).join(':')
        api.brainUpdateEntityPosition(cat, name, node.position.x, node.position.y).catch(() => {})
      }
    },
    [store]
  )

  const loadDetail = useCallback(async (node: Node) => {
    if (node.id.startsWith('entity:')) {
      try {
        const parts = node.id.split(':')
        const cat = parts[1]
        const name = parts.slice(2).join(':')
        const entity = await api.brainEntity(cat, name)
        setDetailEntity(entity)
      } catch {
        setDetailEntity(null)
      }
    } else if (node.id.startsWith('neuron:')) {
      const nrsNode = store.nodes.find((n) => n.id === node.id)
      if (nrsNode) {
        setDetailEntity({
          name: nrsNode.title,
          category: 'Neuron',
          summary: nrsNode.content || '',
          facts: [],
          path: '',
          created_at: '',
          updated_at: '',
        })
      }
    } else {
      setDetailEntity(null)
    }
  }, [store.nodes])

  const handleNodeClick = useCallback(
    (_evt: unknown, node: Node) => {
      store.selectNode(node.id)
      loadDetail(node)
    },
    [store, loadDetail]
  )

  const handlePaneClick = useCallback(() => {
    store.selectNode(null)
    setDetailEntity(null)
    setEditingNode(null)
  }, [store])

  const handleDoubleClick = useCallback((_evt: unknown, node?: Node) => {
    if (node) {
      setEditingNode(node)
      setEditTitle(node.data.label as string)
      setEditContent((node.data.summary as string) || '')
    }
    setShowCreateDialog(true)
  }, [])

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([])
      return
    }
    try {
      const results = await api.brainSearch({ query: searchQuery, category: activeCategory || undefined })
      setSearchResults(results)
    } catch {
      setSearchResults([])
    }
  }

  const handleCreate = async () => {
    if (!createTitle.trim()) return
    if (createMode === 'entity') {
      await store.createEntity(createCategory, createTitle.trim())
    } else {
      await store.createNeuron(createTitle.trim())
    }
    setCreateTitle('')
    setShowCreateDialog(false)
  }

  const handleDeleteSelected = async () => {
    const sid = store.selectedNodeId
    if (!sid) return
    if (sid.startsWith('entity:')) {
      const parts = sid.split(':')
      const cat = parts[1]
      const name = parts.slice(2).join(':')
      await store.deleteEntity(cat, name)
    } else if (sid.startsWith('neuron:')) {
      await store.deleteNeuron(sid)
    }
    setDetailEntity(null)
  }

  const handleAddFact = async () => {
    if (!detailEntity || !newFactText.trim()) return
    try {
      await api.brainAddFact(detailEntity.category, detailEntity.name, {
        text: newFactText.trim(),
        tags: newFactTags,
      })
      setNewFactText('')
      setNewFactTags([])
      setDetailEntity(null)
      store.fetchGraph()
    } catch (e: unknown) {
      console.error('Failed to add fact:', e instanceof Error ? e.message : e)
    }
  }

  const handleRetry = async () => {
    setErrorType('none')
    setInitialLoadComplete(false)
    try {
      await store.fetchGraph()
      setNrsUnavailable(false)
      setErrorType('none')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      if (msg.includes('NRS') || msg.includes('model') || msg.includes('provider')) {
        setErrorType('nrs_missing')
        setNrsUnavailable(true)
      } else {
        setErrorType('connection')
        setNrsUnavailable(false)
      }
    }
    setInitialLoadComplete(true)
  }

  const selectedNode = store.nodes.find((n) => n.id === store.selectedNodeId)

  const categories = [...new Set(entityList.map((e) => e.category))]
  const filteredEntities = activeCategory
    ? entityList.filter((e) => e.category === activeCategory)
    : entityList

  const entityNodes = store.nodes.filter((n) => n.source === 'second_brain' && n.type === 'entity')
  const factNodes = store.nodes.filter((n) => n.source === 'second_brain' && n.type === 'fact' && n.status !== 'contradicted')
  const contradictionNodes = store.nodes.filter((n) => n.source === 'second_brain' && n.type === 'fact' && n.status === 'contradicted')
  const neuronNodes = store.nodes.filter((n) => n.source === 'graph_db')

  return (
    <div className="w-full h-full flex">
      {/* Left Sidebar */}
      {sidebarOpen && (
        <div className="w-72 lg:w-80 bg-cb-surface border-r border-cb-border flex flex-col shrink-0 overflow-hidden">
          <div className="p-3 border-b border-cb-border">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-cb-text-bright uppercase tracking-wider flex items-center gap-1.5">
                <Brain size={14} className="text-cb-neon" /> Knowledge Graph
              </h3>
              <span className="text-[10px] text-cb-muted font-mono">
                {store.nodes.length}n / {store.edges.length}e
              </span>
            </div>
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-cb-muted" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search entities..."
                className="cb-input w-full pl-8 pr-2 py-1.5 text-xs"
              />
            </div>
          </div>

          {/* Category filters */}
          <div className="flex flex-wrap gap-1 p-2 border-b border-cb-border">
            <button
              onClick={() => setActiveCategory('')}
              className={`px-2 py-0.5 text-[10px] rounded-full border transition-all ${
                !activeCategory ? 'border-cb-neon bg-cb-neon/10 text-cb-neon' : 'border-cb-border text-cb-muted hover:border-cb-neon/50'
              }`}
            >
              All
            </button>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveCategory(cat)}
                className={`px-2 py-0.5 text-[10px] rounded-full border transition-all ${
                  activeCategory === cat ? 'border-cb-neon bg-cb-neon/10 text-cb-neon' : 'border-cb-border text-cb-muted hover:border-cb-neon/50'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Entity list */}
          <div className="flex-1 overflow-y-auto">
            {searchResults.length > 0 ? (
              <div className="p-2">
                <h4 className="text-[10px] text-cb-muted font-mono uppercase tracking-wider mb-1 px-2">Search Results</h4>
                {searchResults.map((r, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      const nid = `entity:${r.category}:${r.entity}`
                      store.selectNode(nid)
                      const node = store.nodes.find((n) => n.id === nid)
                      if (node) loadDetail({ id: nid, type: 'entity', data: {} } as Node)
                    }}
                    className="w-full text-left px-2 py-1.5 text-xs hover:bg-cb-card-hover rounded-lg transition-colors"
                  >
                    <span className="text-cb-text-bright">{r.entity}</span>
                    <span className="text-cb-muted ml-1">({r.category})</span>
                    <p className="text-cb-muted/60 text-[10px] truncate mt-0.5">{r.text}</p>
                  </button>
                ))}
              </div>
            ) : (
              <div>
                <div className="px-3 py-2 text-[10px] text-cb-muted font-mono uppercase tracking-wider flex items-center justify-between">
                  <span>Entities ({entityNodes.length})</span>
                  <span className="text-cb-muted/40">Facts ({factNodes.length})</span>
                </div>
                {filteredEntities.map((e) => (
                  <button
                    key={`${e.category}:${e.name}`}
                    onClick={() => {
                      const nid = `entity:${e.category}:${e.name}`
                      store.selectNode(nid)
                      const node = store.nodes.find((n) => n.id === nid)
                      if (node) loadDetail({ id: nid, type: 'entity', data: {} } as Node)
                    }}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-cb-card-hover transition-colors border-l-2 ${
                      store.selectedNodeId === `entity:${e.category}:${e.name}`
                        ? 'border-cb-neon bg-cb-neon/5'
                        : 'border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-cb-text-bright flex items-center gap-1.5">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: CATEGORY_COLORS[e.category] || CATEGORY_COLORS.default }}
                        />
                        {e.name}
                      </span>
                      <span className="text-[10px] text-cb-muted">{e.facts_count}f</span>
                    </div>
                    {e.summary_preview && (
                      <p className="text-cb-muted/60 text-[10px] truncate mt-0.5">{e.summary_preview}</p>
                    )}
                  </button>
                ))}

                {neuronNodes.length > 0 && (
                  <>
                    <div className="px-3 py-2 mt-2 text-[10px] text-cb-muted font-mono uppercase tracking-wider border-t border-cb-border/50">
                      Graph Neurons ({neuronNodes.length})
                    </div>
                    {neuronNodes.map((n) => (
                      <button
                        key={n.id}
                        onClick={() => {
                          store.selectNode(n.id)
                          loadDetail({ id: n.id, type: 'neuron', data: {} } as Node)
                        }}
                        className={`w-full text-left px-3 py-2 text-xs hover:bg-cb-card-hover transition-colors border-l-2 ${
                          store.selectedNodeId === n.id
                            ? 'border-cb-cyan bg-cb-cyan/5'
                            : 'border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-sm bg-cb-cyan shadow-cyan-sm" />
                          <span className="font-medium text-cb-text-bright">{n.title}</span>
                        </div>
                      </button>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Sidebar bottom actions */}
          <div className="p-2 border-t border-cb-border flex gap-1">
            <button
              onClick={() => { setCreateMode('entity'); setCreateTitle(''); setShowCreateDialog(true) }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs cb-btn-neon rounded-lg"
            >
              <Plus size={12} /> Entity
            </button>
            <button
              onClick={() => { setCreateMode('neuron'); setCreateTitle(''); setShowCreateDialog(true) }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs cb-btn-cyan rounded-lg"
            >
              <Plus size={12} /> Neuron
            </button>
          </div>
        </div>
      )}

      {/* Center: Graph canvas */}
      <div className="flex-1 relative min-h-[500px]">
        {/* Toolbar */}
        <div className="absolute top-3 left-3 z-10 flex gap-1.5">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className={`flex items-center gap-1 px-2 py-1.5 text-xs rounded-lg transition-all ${
              sidebarOpen ? 'bg-cb-neon/20 text-cb-neon border border-cb-neon/30' : 'cb-btn-neon'
            }`}
            title="Toggle sidebar"
          >
            <ChevronRight size={14} className={sidebarOpen ? 'rotate-180' : ''} />
          </button>
          <button
            onClick={handleAutoLayout}
            disabled={layouting}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs cb-btn-cyan rounded-lg disabled:opacity-30"
            title="Auto-layout"
          >
            <LayoutIcon size={14} /> {layouting ? 'Layouting...' : 'Auto Layout'}
          </button>
          {store.selectedNodeId && (
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-cb-red/30 bg-cb-red/10 text-cb-red hover:bg-cb-red/20 transition-all"
              title="Delete selected"
            >
              <Trash2 size={14} /> Delete
            </button>
          )}
          <button
            onClick={() => {
              if (confirm("Delete ALL neurons, entities, facts and vectors? This cannot be undone.")) {
                store.resetAll()
              }
            }}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border border-cb-red/30 bg-cb-red/10 text-cb-red hover:bg-cb-red/20 transition-all"
            title="Reset NRS"
          >
            <RotateCcw size={14} /> Reset
          </button>
        </div>

        {/* Loading / Error overlays */}
        {!initialLoadComplete && (
          <div className="absolute inset-0 flex items-center justify-center bg-cb-bg/80 backdrop-blur-sm z-20">
            <div className="text-center">
              <div className="w-8 h-8 border-4 border-cb-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-cb-muted text-sm">Loading Neural Graph...</p>
            </div>
          </div>
        )}

        {initialLoadComplete && errorType === 'connection' && (
          <div className="absolute inset-0 flex items-center justify-center bg-cb-bg/80 backdrop-blur-sm z-20">
            <div className="text-center max-w-md p-6 bg-cb-card border border-cb-red/30 rounded-xl">
              <WifiOff size={32} className="text-cb-red mx-auto mb-3" />
              <h3 className="text-cb-text-bright font-semibold mb-2">Connection Failed</h3>
              <p className="text-cb-muted text-xs mb-4">
                Unable to reach the Neural Recall System backend. The NRS service may be offline or unreachable.
              </p>
              <button
                onClick={handleRetry}
                className="cb-btn-neon px-4 py-2 text-xs rounded-lg"
              >
                Retry Connection
              </button>
            </div>
          </div>
        )}

        {initialLoadComplete && errorType === 'nrs_missing' && (
          <div className="absolute inset-0 flex items-center justify-center bg-cb-bg/80 backdrop-blur-sm z-20">
            <div className="text-center max-w-md p-6 bg-cb-card border border-cb-gold/30 rounded-xl">
              <Brain size={32} className="text-cb-gold mx-auto mb-3" />
              <h3 className="text-cb-text-bright font-semibold mb-2">NRS Unavailable</h3>
              <p className="text-cb-muted text-xs mb-4">
                The Neural Recall System requires a model provider (Ollama, vLLM, or OpenAI) to be running.
                Please start a provider and ensure a model is available, then retry.
              </p>
              <button
                onClick={handleRetry}
                className="cb-btn-neon px-4 py-2 text-xs rounded-lg"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {/* ReactFlow canvas - only render when no errors and data loaded */}
        {initialLoadComplete && errorType === 'none' && !nrsUnavailable && (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={handleConnect}
            onNodeClick={handleNodeClick}
            onNodeDragStop={handleNodeDragStop}
            onPaneClick={handlePaneClick}
            onNodeDoubleClick={handleDoubleClick}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            defaultEdgeOptions={{ animated: true }}
            proOptions={{ hideAttribution: true }}
            selectionMode={SelectionMode.Partial}
            className="bg-cb-bg"
          >
            <Background color="#2a2a40" gap={20} />
            <Controls className="!bg-cb-card !border-cb-border" />
            <MiniMap
              nodeColor={(n) => CATEGORY_COLORS[(n.data as { category?: string }).category || ''] || CATEGORY_COLORS.default}
              className="!bg-cb-card !border-cb-border"
              maskColor="rgba(10, 10, 20, 0.7)"
            />
          </ReactFlow>
        )}
      </div>

      {/* Right: Detail panel */}
      {detailEntity && (
        <div className="w-80 bg-cb-surface border-l border-cb-border flex flex-col shrink-0 overflow-hidden">
          <div className="p-3 border-b border-cb-border flex items-center justify-between">
            <h3 className="text-xs font-semibold text-cb-text-bright uppercase tracking-wider">
              Entity Details
            </h3>
            <button
              onClick={() => setDetailEntity(null)}
              className="text-cb-muted hover:text-cb-text"
            >
              <X size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            <div>
              <div className="text-[10px] text-cb-muted font-mono uppercase tracking-wider mb-1">Name</div>
              <div className="text-sm text-cb-text-bright">{detailEntity.name}</div>
            </div>
            <div>
              <div className="text-[10px] text-cb-muted font-mono uppercase tracking-wider mb-1">Category</div>
              <div className="text-sm text-cb-text-bright flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLORS[detailEntity.category] || CATEGORY_COLORS.default }}
                />
                {detailEntity.category}
              </div>
            </div>
            {detailEntity.summary && (
              <div>
                <div className="text-[10px] text-cb-muted font-mono uppercase tracking-wider mb-1">Summary</div>
                <p className="text-xs text-cb-text leading-relaxed">{detailEntity.summary}</p>
              </div>
            )}
            {detailEntity.facts && detailEntity.facts.length > 0 && (
              <div>
                <div className="text-[10px] text-cb-muted font-mono uppercase tracking-wider mb-1">
                  Facts ({detailEntity.facts.length})
                </div>
                <div className="space-y-1.5">
                  {detailEntity.facts.map((f, i) => (
                    <div key={i} className="text-xs text-cb-text p-2 bg-cb-bg rounded-lg border border-cb-border">
                      {f.text}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Add fact editor */}
            <div className="pt-2 border-t border-cb-border">
              {showFactEditor ? (
                <div className="space-y-2">
                  <textarea
                    value={newFactText}
                    onChange={(e) => setNewFactText(e.target.value)}
                    placeholder="Enter fact..."
                    className="cb-input w-full text-xs p-2 resize-none"
                    rows={3}
                  />
                  <input
                    value={newFactTags.join(', ')}
                    onChange={(e) => setNewFactTags(e.target.value.split(',').map(t => t.trim()).filter(Boolean))}
                    placeholder="tags (comma-separated)"
                    className="cb-input w-full text-xs p-2"
                  />
                  <div className="flex gap-1">
                    <button
                      onClick={handleAddFact}
                      className="flex-1 cb-btn-neon px-2 py-1.5 text-xs rounded-lg"
                    >
                      Add Fact
                    </button>
                    <button
                      onClick={() => { setShowFactEditor(false); setNewFactText(''); setNewFactTags([]) }}
                      className="px-2 py-1.5 text-xs text-cb-muted hover:text-cb-text rounded-lg"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowFactEditor(true)}
                  className="w-full flex items-center justify-center gap-1 py-1.5 text-xs text-cb-cyan hover:bg-cb-cyan/10 rounded-lg transition-colors"
                >
                  <Plus size={12} /> Add Fact
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit dialog */}
      {showCreateDialog && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
          onClick={() => setShowCreateDialog(false)}
        >
          <div
            className="bg-cb-card border border-cb-border rounded-xl p-6 w-96 shadow-neon"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-cb-text-bright">
                {editingNode ? 'Edit Node' : `Create ${createMode === 'entity' ? 'Entity' : 'Neuron'}`}
              </h2>
              <button onClick={() => { setShowCreateDialog(false); setEditingNode(null) }} className="text-cb-muted hover:text-cb-text">
                <X size={18} />
              </button>
            </div>
            <div className="space-y-3">
              {createMode === 'entity' && !editingNode && (
                <div>
                  <label className="text-xs text-cb-muted font-mono uppercase tracking-wider">Category</label>
                  <select
                    value={createCategory}
                    onChange={(e) => setCreateCategory(e.target.value)}
                    className="cb-input w-full text-sm p-2 mt-1"
                  >
                    <option value="concept">Concept</option>
                    <option value="person">Person</option>
                    <option value="organization">Organization</option>
                    <option value="project">Project</option>
                    <option value="event">Event</option>
                    <option value="location">Location</option>
                    <option value="technology">Technology</option>
                  </select>
                </div>
              )}
              <div>
                <label className="text-xs text-cb-muted font-mono uppercase tracking-wider">
                  {createMode === 'entity' ? 'Name' : 'Title'}
                </label>
                <input
                  value={editTitle || createTitle}
                  onChange={(e) => {
                    if (editingNode) setEditTitle(e.target.value)
                    else setCreateTitle(e.target.value)
                  }}
                  placeholder={createMode === 'entity' ? 'Entity name...' : 'Neuron title...'}
                  className="cb-input w-full text-sm p-2 mt-1"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs text-cb-muted font-mono uppercase tracking-wider">
                  {createMode === 'entity' ? 'Summary (optional)' : 'Content (optional)'}
                </label>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  placeholder={createMode === 'entity' ? 'Brief summary...' : 'Neuron content...'}
                  className="cb-input w-full text-sm p-2 mt-1 resize-none"
                  rows={3}
                />
              </div>
              <button
                onClick={() => {
                  if (editingNode) {
                    if (editingNode.id.startsWith('neuron:')) {
                      store.updateNeuron(editingNode.id, { title: editTitle, content: editContent })
                    }
                    setEditingNode(null)
                    setShowCreateDialog(false)
                  } else {
                    handleCreate()
                  }
                }}
                className="w-full cb-btn-neon py-2 text-sm rounded-lg"
              >
                {editingNode ? 'Save Changes' : `Create ${createMode === 'entity' ? 'Entity' : 'Neuron'}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function NRSPanel() {
  return (
    <ReactFlowProvider>
      <NRSPanelInner />
    </ReactFlowProvider>
  )
}
