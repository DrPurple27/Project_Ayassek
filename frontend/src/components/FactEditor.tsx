import { useState } from 'react'
import { Pencil, Trash2, ChevronUp, History } from 'lucide-react'
import type { BrainFact } from '@/api/client'
import { SEMANTIC_TAGS } from '@/store/secondBrain'

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-cb-neon/15 text-cb-neon border border-cb-neon/30',
  superseded: 'bg-cb-gold/15 text-cb-gold border border-cb-gold/30',
  contradicted: 'bg-cb-red/15 text-cb-red border border-cb-red/30',
  uncertain: 'bg-cb-muted/15 text-cb-muted border border-cb-border',
}

interface Props {
  fact: BrainFact
  category: string
  entityName: string
  onSave: (factId: string, body: { text?: string; status?: string; tags?: string[] }) => Promise<void>
  onDelete: (factId: string) => Promise<void>
}

export default function FactEditor({ fact, category: _category, entityName: _entityName, onSave, onDelete }: Props) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(fact.text)
  const [editStatus, setEditStatus] = useState(fact.status)
  const [editTags, setEditTags] = useState<string[]>(fact.tags)
  const [showHistory, setShowHistory] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    await onSave(fact.id, { text: editText, status: editStatus, tags: editTags })
    setSaving(false)
    setEditing(false)
  }

  const handleDelete = async () => {
    await onDelete(fact.id)
  }

  const toggleTag = (tag: string) => {
    setEditTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  return (
    <div className="cb-panel rounded-lg p-3 group">
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[editStatus] || STATUS_COLORS['uncertain']}`}>
          {editStatus}
        </span>
        <div className="flex-1" />
        {!editing && (
          <>
            <button
              onClick={() => {
                setEditText(fact.text)
                setEditStatus(fact.status)
                setEditTags(fact.tags)
                setEditing(true)
              }}
              className="opacity-0 group-hover:opacity-100 text-cb-muted hover:text-cb-neon p-0.5 transition-all"
              title="Edit"
            >
              <Pencil size={14} />
            </button>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="opacity-0 group-hover:opacity-100 text-cb-muted hover:text-cb-cyan p-0.5 transition-all"
              title="Version history"
            >
              {showHistory ? <ChevronUp size={14} /> : <History size={14} />}
            </button>
            {!confirmDelete ? (
              <button
                onClick={() => setConfirmDelete(true)}
                className="opacity-0 group-hover:opacity-100 text-cb-muted hover:text-cb-red p-0.5 transition-all"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            ) : (
              <span className="flex items-center gap-1 text-xs">
                <button onClick={handleDelete} className="text-cb-red hover:underline">Confirm</button>
                <button onClick={() => setConfirmDelete(false)} className="text-cb-muted hover:underline">No</button>
              </span>
            )}
          </>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            rows={3}
            autoFocus
            className="cb-input w-full resize-none"
          />
          <div className="flex flex-wrap gap-1">
            {SEMANTIC_TAGS.map((tag) => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`text-xs px-2 py-0.5 rounded-full border transition-all ${
                  editTags.includes(tag)
                    ? 'bg-cb-neon/20 border-cb-neon text-cb-neon shadow-neon-sm'
                    : 'border-cb-border text-cb-muted hover:border-cb-neon/30'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <select
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value)}
              className="cb-input text-xs py-1 px-2"
            >
              <option value="active">Active</option>
              <option value="superseded">Superseded</option>
              <option value="contradicted">Contradicted</option>
              <option value="uncertain">Uncertain</option>
            </select>
            <div className="flex-1" />
            <button
              onClick={() => setEditing(false)}
              className="px-3 py-1 text-xs text-cb-muted hover:text-cb-text-bright rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !editText.trim()}
              className="cb-btn-neon text-xs px-3 py-1 rounded-lg disabled:opacity-30"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm leading-relaxed">{fact.text}</p>
      )}

      {!editing && fact.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {fact.tags.map((tag) => (
            <span key={tag} className="text-xs bg-cb-neon/10 text-cb-neon px-1.5 py-0.5 rounded border border-cb-neon/20">
              {tag}
            </span>
          ))}
        </div>
      )}

      {showHistory && fact.version_history?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-cb-border space-y-2">
          <p className="text-xs text-cb-muted font-medium font-mono uppercase tracking-wider">Version History</p>
          {fact.version_history.map((v, i) => (
            <div key={i} className="bg-cb-bg border border-cb-border rounded p-2 text-xs space-y-1">
              <div className="flex gap-2 text-cb-muted font-mono">
                <span>v{i + 1}</span>
                <span>{v.status}</span>
                <span>{new Date(v.timestamp).toLocaleString()}</span>
              </div>
              <p className="text-cb-text line-clamp-2">{v.text}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2 mt-1 text-[10px] text-cb-muted/40 font-mono">
        <span>{new Date(fact.timestamp).toLocaleString()}</span>
        <span>&#x2022;</span>
        <span>{fact.source}</span>
        <span>&#x2022;</span>
        <span>id: {fact.id.slice(0, 6)}</span>
      </div>
    </div>
  )
}
