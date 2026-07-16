import { useState, useCallback } from 'react'
import { Search, ChevronDown, ChevronUp, ExternalLink, Copy } from 'lucide-react'
import { useRagStore } from '@/store/rag'

export default function QueryTester() {
  const { queryResult, loading, error, query } = useRagStore()
  const [queryText, setQueryText] = useState('')
  const [rerank, setRerank] = useState(true)
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})

  const handleQuery = useCallback(async () => {
    if (!queryText.trim()) return
    await query(queryText.trim(), rerank)
  }, [query, queryText, rerank])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleQuery()
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const scoreColor = (score: number) => {
    if (score > 0.8) return 'text-cb-green'
    if (score > 0.5) return 'text-cb-gold'
    return 'text-cb-muted'
  }

  return (
    <div className="cb-panel rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium flex items-center gap-2 text-cb-text-bright">
          <Search size={16} className="text-cb-cyan" />
          Query Tester
        </h2>
        <label className="flex items-center gap-1 text-xs text-cb-muted">
          <input
            type="checkbox"
            checked={rerank}
            onChange={e => setRerank(e.target.checked)}
            className="rounded border-cb-border bg-cb-bg text-cb-neon focus:ring-cb-neon accent-[#8C52FF]"
          />
          Rerank
        </label>
      </div>

      <div className="flex gap-2 mb-3">
        <input
          value={queryText}
          onChange={e => setQueryText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a query to test retrieval..."
          className="cb-input flex-1"
        />
        <button
          onClick={handleQuery}
          disabled={!queryText.trim() || loading}
          className="cb-btn-cyan px-3 py-2 text-sm disabled:opacity-30"
        >
          Search
        </button>
      </div>

      {error && (
        <div className="mb-3 p-2 bg-cb-red/10 border border-cb-red/30 rounded-lg text-sm text-cb-red">
          {error}
        </div>
      )}

      {queryResult && (
        <div className="space-y-2">
          <p className="text-xs text-cb-muted font-mono uppercase tracking-wider">
            {queryResult.reranked?.length ?? 0} results from {queryResult.chunks?.length ?? 0} candidates
          </p>

          <div className="max-h-64 overflow-y-auto space-y-2">
            {queryResult.reranked?.map((r: any, i: number) => (
              <div
                key={i}
                className="bg-cb-bg border border-cb-border rounded-lg p-3 hover:border-cb-neon/20 transition-all"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-cb-neon font-mono">#{i + 1}</span>
                  <span className="text-xs text-cb-muted">{r.source}</span>
                  {r.rerank_score != null && (
                    <span className={`text-xs font-mono font-bold ${scoreColor(r.rerank_score)}`}>
                      {(r.rerank_score * 100).toFixed(0)}%
                    </span>
                  )}
                  <ExternalLink size={12} className="text-cb-muted/60" />
                </div>
                <p className="text-sm leading-relaxed line-clamp-3">{r.text}</p>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => setExpanded(prev => ({ ...prev, [i]: !prev[i] }))}
                    className="text-xs text-cb-muted hover:text-cb-cyan flex items-center gap-1 transition-colors"
                  >
                    {expanded[i] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    Toggle
                  </button>
                  <button
                    onClick={() => copyToClipboard(r.text)}
                    className="text-xs text-cb-muted hover:text-cb-neon flex items-center gap-1 transition-colors"
                  >
                    <Copy size={12} />
                    Copy
                  </button>
                </div>
              </div>
            ))}
          </div>

          {expanded[0] && queryResult.reranked && (
            <details className="mt-2">
              <summary className="text-xs text-cb-muted cursor-pointer hover:text-cb-cyan transition-colors">Show context preview</summary>
              <pre className="mt-2 p-2 bg-cb-bg border border-cb-border rounded text-xs text-cb-muted overflow-x-auto whitespace-pre-wrap">
                {queryResult.context}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
