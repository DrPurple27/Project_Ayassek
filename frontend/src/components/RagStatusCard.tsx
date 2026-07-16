import { Database, Cpu, Network, Activity, Zap, Settings } from 'lucide-react'
import { useRagStore } from '@/store/rag'

export default function RagStatusCard() {
  const { status, loading, fetchStatus } = useRagStore()

  const statItems = status ? [
    { icon: Database, label: 'Vectors', value: status.vector_count?.toLocaleString() ?? 'N/A', color: 'text-cb-cyan' },
    { icon: Cpu, label: 'Embedding', value: status.embedding_model?.split('/').pop() ?? 'N/A', color: 'text-cb-neon' },
    { icon: Network, label: 'Chunking', value: status.chunking_strategy ?? 'N/A', color: 'text-cb-gold' },
    { icon: Zap, label: 'Reranker', value: status.reranker_enabled ? `On (${status.reranker_model?.split('/').pop() ?? ''})` : 'Off', color: status.reranker_enabled ? 'text-cb-green' : 'text-cb-muted' },
  ] : []

  return (
    <div className="cb-panel rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium flex items-center gap-2 text-cb-text-bright">
          <Activity size={16} className="text-cb-cyan" />
          Pipeline Status
        </h2>
        <button
          onClick={fetchStatus}
          disabled={loading}
          className="p-1.5 text-cb-muted hover:text-cb-neon rounded transition-colors"
          title="Refresh"
        >
          <Settings size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="bg-cb-bg rounded-lg p-3 animate-pulse border border-cb-border">
              <div className="h-4 bg-cb-border rounded w-3/4 mb-2" />
              <div className="h-3 bg-cb-border rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {statItems.map((item, i) => (
            <div key={i} className="bg-cb-bg border border-cb-border rounded-lg p-3 hover:border-cb-neon/20 transition-all">
              <div className="flex items-center gap-2 mb-1">
                <item.icon size={14} className={item.color} />
                <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">{item.label}</span>
              </div>
              <p className="font-medium text-sm truncate text-cb-text-bright">{item.value}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
