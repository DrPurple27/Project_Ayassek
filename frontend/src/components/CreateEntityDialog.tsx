import { useState } from 'react'
import { X } from 'lucide-react'
import { useSecondBrainStore } from '@/store/secondBrain'

const CATEGORIES = ['projects', 'people', 'concepts', 'meetings', 'references', 'tasks']

interface Props {
  open: boolean
  onClose: () => void
}

export default function CreateEntityDialog({ open, onClose }: Props) {
  const { createEntity, loading } = useSecondBrainStore()
  const [name, setName] = useState('')
  const [category, setCategory] = useState('projects')
  const [summary, setSummary] = useState('')

  if (!open) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await createEntity(name.trim(), category, summary.trim())
    setName('')
    setSummary('')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-cb-bg/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-cb-card border border-cb-neon/20 rounded-xl w-full max-w-md mx-4 shadow-neon"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-cb-border">
          <h2 className="text-sm font-semibold text-cb-text-bright cb-text-glow">New Entity</h2>
          <button onClick={onClose} className="text-cb-muted hover:text-cb-cyan transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-xs text-cb-muted mb-1 uppercase tracking-wider font-mono">Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Raphael"
              autoFocus
              className="cb-input w-full"
            />
          </div>

          <div>
            <label className="block text-xs text-cb-muted mb-1 uppercase tracking-wider font-mono">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="cb-input w-full"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-cb-muted mb-1 uppercase tracking-wider font-mono">Summary</label>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Brief description..."
              rows={4}
              className="cb-input w-full resize-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 text-sm text-cb-muted hover:text-cb-text-bright rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="cb-btn-neon px-4 py-2 text-sm rounded-lg disabled:opacity-30"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
