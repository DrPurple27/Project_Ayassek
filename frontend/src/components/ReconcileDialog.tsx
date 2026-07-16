import { useState } from 'react'
import { X, AlertTriangle } from 'lucide-react'

interface Conflict {
  existingFact: { id: string; text: string; status: string }
  newFact: { text: string; tags?: string[] }
  reasoning: string
}

interface Props {
  conflict: Conflict | null
  onResolve: (action: 'keep_both' | 'supersede_existing' | 'ignore') => void
  onClose: () => void
}

export default function ReconcileDialog({ conflict, onResolve, onClose }: Props) {
  const [resolving, setResolving] = useState(false)

  if (!conflict) return null

  const handleResolve = async (action: 'keep_both' | 'supersede_existing' | 'ignore') => {
    setResolving(true)
    await onResolve(action)
    setResolving(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-cb-bg/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-cb-card border border-cb-neon/20 rounded-xl w-full max-w-lg mx-4 shadow-neon"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-cb-border">
          <h2 className="text-sm font-semibold flex items-center gap-2 text-cb-text-bright cb-text-glow">
            <AlertTriangle size={16} className="text-cb-gold" />
            Memory Conflict Detected
          </h2>
          <button onClick={onClose} className="text-cb-muted hover:text-cb-cyan transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-xs text-cb-muted">{conflict.reasoning}</p>

          <div className="bg-cb-bg border border-cb-red/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] text-cb-red font-medium uppercase font-mono tracking-wider">Existing</span>
              <span className="text-[10px] text-cb-muted font-mono">id: {conflict.existingFact.id.slice(0, 6)}</span>
              <span className="text-[10px] text-cb-muted">{conflict.existingFact.status}</span>
            </div>
            <p className="text-sm text-cb-text">{conflict.existingFact.text}</p>
          </div>

          <div className="bg-cb-bg border border-cb-green/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] text-cb-green font-medium uppercase font-mono tracking-wider">New</span>
            </div>
            <p className="text-sm text-cb-text">{conflict.newFact.text}</p>
          </div>

          <div className="flex flex-col gap-2 pt-2">
            <button
              onClick={() => handleResolve('keep_both')}
              disabled={resolving}
              className="cb-btn-neon w-full py-2 text-sm disabled:opacity-30"
            >
              Keep Both
            </button>
            <button
              onClick={() => handleResolve('supersede_existing')}
              disabled={resolving}
              className="cb-btn-gold w-full py-2 text-sm disabled:opacity-30"
            >
              Replace Existing (mark as superseded)
            </button>
            <button
              onClick={() => handleResolve('ignore')}
              disabled={resolving}
              className="w-full px-4 py-2 text-sm text-cb-muted hover:text-cb-text-bright border border-cb-border rounded-lg transition-colors disabled:opacity-30"
            >
              Ignore (keep both unchanged)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
