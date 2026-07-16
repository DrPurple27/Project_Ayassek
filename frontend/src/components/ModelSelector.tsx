import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Loader2, Zap, Check } from 'lucide-react'
import { api } from '@/api/client'
import { useChatStore } from '@/store/chat'

interface ModelSelectorProps {
  sessionId: string | null
  className?: string
}

interface ProviderModel {
  id: string
  object: string
  created: number
  owned_by: string
}

interface ProviderInfo {
  id: string
  name: string
  models: ProviderModel[]
}

export default function ModelSelector({ sessionId, className = '' }: ModelSelectorProps) {
  const [open, setOpen] = useState(false)
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [activeProvider, setActiveProvider] = useState<string>('')
  const [activeModel, setActiveModel] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [modelsLoading, setModelsLoading] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { sessions } = useChatStore()

  useEffect(() => {
    api.getProviders().then((res) => {
      setProviders(res.providers)
      setActiveProvider(res.active_provider)
      setActiveModel(res.active_model)
    }).catch((err) => {
      console.error('Failed to load providers:', err)
    })
  }, [])

  const handleProviderSelect = async (providerId: string) => {
    setModelsLoading(providerId)
    try {
      const res = await api.getModels(providerId)
      const models = res.models || []
      const modelIds = models.map((m: ProviderModel) => m.id)
      if (modelIds.length > 0) {
        await api.setActiveProvider(providerId, modelIds[0])
        setActiveProvider(providerId)
        setActiveModel(modelIds[0])
      }
    } catch (err: unknown) {
      console.error('Failed to load models:', err instanceof Error ? err.message : err)
    } finally {
      setModelsLoading(null)
    }
  }

  const handleModelSelect = async (modelId: string) => {
    setLoading(true)
    try {
      await api.setActiveProvider(activeProvider, modelId)
      setActiveModel(modelId)
      setOpen(false)
    } catch (err: unknown) {
      console.error('Failed to set model:', err instanceof Error ? err.message : err)
    } finally {
      setLoading(false)
    }
  }

  const handleOutsideClick = (e: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
      setOpen(false)
    }
  }

  useEffect(() => {
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  const currentSession = sessions.find((s) => s.id === sessionId)

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs cb-btn-cyan rounded-lg transition-all hover:shadow-cyan-sm disabled:opacity-30"
        disabled={loading || !!modelsLoading}
        title="Select provider/model"
      >
        <Zap size={12} className="text-cb-cyan" />
        <span className="truncate max-w-[120px] font-mono">{activeProvider} / {activeModel}</span>
        <ChevronDown size={12} className={`${open ? 'rotate-180' : ''} transition-transform text-cb-muted`} />
        {loading && <Loader2 size={12} className="animate-spin text-cb-cyan" />}
      </button>

      {open && (
        <div
          ref={dropdownRef}
          className="absolute right-0 top-full mt-1.5 bg-cb-card border border-cb-border rounded-xl shadow-neon z-40 min-w-[240px] overflow-hidden animate-slide-in"
        >
          <div className="px-3 py-2 border-b border-cb-border bg-cb-surface/80 backdrop-blur-sm">
            <p className="text-[10px] text-cb-muted uppercase tracking-wider font-mono">Provider</p>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {providers.map((p) => (
              <div key={p.id} className="p-1">
                <button
                  onClick={() => handleProviderSelect(p.id)}
                  disabled={modelsLoading === p.id || loading}
                  className={`w-full flex items-center gap-2 px-2.5 py-2 text-xs rounded-lg transition-all ${
                    activeProvider === p.id
                      ? 'bg-cb-neon/10 text-cb-neon border border-cb-neon/30 shadow-neon-sm'
                      : 'text-cb-text hover:bg-cb-card-hover hover:border-cb-border border border-transparent'
                  }`}
                >
                  <span className="flex-1 truncate font-medium">{p.name || p.id}</span>
                  {activeProvider === p.id && <Check size={12} className="text-cb-neon shrink-0" />}
                  {modelsLoading === p.id && <Loader2 size={12} className="animate-spin text-cb-cyan shrink-0" />}
                </button>
                {activeProvider === p.id && p.models.length > 0 && (
                  <div className="ml-2 mt-1 space-y-1 border-l border-cb-border/50 pl-2">
                    {p.models.slice(0, 10).map((m) => (
                      <button
                        key={m.id}
                        onClick={() => handleModelSelect(m.id)}
                        disabled={loading}
                        className={`w-full flex items-center gap-2 px-2 py-1.5 text-[11px] rounded transition-all ${
                          activeModel === m.id
                            ? 'bg-cb-gold/10 text-cb-gold border border-cb-gold/30 shadow-gold'
                            : 'text-cb-muted hover:bg-cb-card-hover hover:text-cb-text'
                        }`}
                      >
                        <span className="flex-1 truncate font-mono">{m.id}</span>
                        {activeModel === m.id && <Check size={10} className="text-cb-gold shrink-0" />}
                      </button>
                    ))}
                    {p.models.length > 10 && (
                      <p className="px-2 py-1 text-[10px] text-cb-muted/60">+{p.models.length - 10} more models</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="px-3 py-2 border-t border-cb-border bg-cb-surface/80 backdrop-blur-sm">
            <p className="text-[10px] text-cb-muted font-mono uppercase tracking-wider">
              Session: {currentSession?.name || sessionId || 'default'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}