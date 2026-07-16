import { useState, useEffect, useRef, useCallback } from 'react'
import { Search, X, ExternalLink } from 'lucide-react'
import { useSecondBrainStore } from '@/store/secondBrain'
import type { SearchResult } from '@/api/client'

interface Props {
  onSelectResult?: (result: SearchResult) => void
}

export default function SearchBar({ onSelectResult }: Props) {
  const { searchResults, search, clearSearch, loading } = useSecondBrainStore()
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleSearch = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      search(q)
    }, 300)
  }, [search])

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const handleChange = (value: string) => {
    setQuery(value)
    if (!value.trim()) {
      clearSearch()
      return
    }
    handleSearch(value)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setQuery('')
      clearSearch()
      inputRef.current?.blur()
    }
  }

  const scoreColor = (score: number) => {
    if (score > 0.8) return 'text-cb-green'
    if (score > 0.5) return 'text-cb-gold'
    return 'text-cb-muted'
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search size={16} className="absolute left-3 top-2.5 text-cb-muted" />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setTimeout(() => setFocused(false), 200)}
          placeholder="Search entities and facts... (Ctrl+K)"
          className="cb-input w-full pl-9 pr-8"
        />
        {query && (
          <button
            onClick={() => { setQuery(''); clearSearch() }}
            className="absolute right-3 top-2.5 text-cb-muted hover:text-cb-text-bright transition-colors"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {focused && searchResults.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-cb-card border border-cb-neon/20 rounded-xl shadow-neon max-h-96 overflow-y-auto z-40">
          <div className="p-2 text-[10px] text-cb-muted uppercase tracking-wider border-b border-cb-border px-3 py-1.5 font-mono">
            Search Results ({searchResults.length})
          </div>
          {searchResults.map((r, i) => (
            <button
              key={`${r.fact_id}-${i}`}
              onMouseDown={() => {
                onSelectResult?.(r)
                setQuery('')
                clearSearch()
              }}
              className="w-full flex items-start gap-3 px-3 py-2.5 text-left hover:bg-cb-card-hover border-b border-cb-border last:border-0 transition-colors"
            >
              <div className={`text-xs font-mono font-bold mt-0.5 ${scoreColor(r.score)}`}>
                {(r.score * 100).toFixed(0)}%
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 text-xs mb-0.5">
                  <span className="text-cb-cyan font-medium">{r.entity}</span>
                  <span className="text-cb-muted/60">in</span>
                  <span className="text-cb-muted capitalize">{r.category}</span>
                  <ExternalLink size={10} className="text-cb-muted/40" />
                </div>
                <p className="text-sm text-cb-text line-clamp-2">{r.text}</p>
              </div>
            </button>
          ))}
        </div>
      )}

      {loading && query && (
        <div className="absolute right-10 top-2.5">
          <div className="w-4 h-4 border-2 border-cb-border border-t-cb-neon rounded-full animate-spin" />
        </div>
      )}
    </div>
  )
}
