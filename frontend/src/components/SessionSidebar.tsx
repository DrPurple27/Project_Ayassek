import { useState, useEffect } from 'react'
import { Plus, Trash2, Pencil, Check, X, MessageSquare } from 'lucide-react'
import { useChatStore } from '@/store/chat'

export default function SessionSidebar() {
  const {
    sessions,
    sessionId,
    fetchSessions,
    createSession,
    deleteSession,
    renameSession,
    switchSession,
  } = useChatStore()

  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const handleCreate = async () => {
    await createSession()
  }

  const handleSwitch = (id: string) => {
    if (id !== sessionId) switchSession(id)
  }

  const handleRenameStart = (id: string, currentName: string) => {
    setRenamingId(id)
    setRenameValue(currentName)
  }

  const handleRenameConfirm = async () => {
    if (renamingId && renameValue.trim()) {
      await renameSession(renamingId, renameValue.trim())
    }
    setRenamingId(null)
  }

  const handleRenameCancel = () => {
    setRenamingId(null)
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    await deleteSession(id)
  }

  const formatTime = (ts: number) => {
    if (!ts) return ''
    const d = new Date(ts * 1000)
    const now = new Date()
    if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }

  return (
    <div className="flex flex-col h-full w-56 bg-cb-bg border-l border-cb-border">
      <div className="flex items-center justify-between px-3 py-2 border-b border-cb-border">
        <span className="text-[10px] font-semibold text-cb-muted uppercase tracking-widest font-mono">Sessions</span>
        <button
          onClick={handleCreate}
          className="p-1 text-cb-muted hover:text-cb-neon rounded transition-colors"
          title="New session"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => handleSwitch(s.id)}
            className={`group flex items-center gap-2 px-3 py-2 cursor-pointer transition-all ${
              sessionId === s.id
                ? 'bg-cb-neon/10 text-cb-text-bright border-l-2 border-cb-neon'
                : 'text-cb-muted hover:text-cb-text hover:bg-cb-card-hover'
            }`}
          >
            <MessageSquare size={14} className="shrink-0 opacity-60" />
            <div className="flex-1 min-w-0">
              {renamingId === s.id ? (
                <div className="flex items-center gap-1">
                  <input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleRenameConfirm()
                      if (e.key === 'Escape') handleRenameCancel()
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="cb-input flex-1 text-xs min-w-0 py-0.5 px-1.5"
                    autoFocus
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); handleRenameConfirm() }}
                    className="p-0.5 text-cb-green hover:text-cb-green"
                  >
                    <Check size={12} />
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleRenameCancel() }}
                    className="p-0.5 text-cb-red hover:text-cb-red"
                  >
                    <X size={12} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <span className="text-xs truncate">{s.name}</span>
                  <span className="text-[9px] text-cb-muted/40 shrink-0 ml-1 font-mono">{formatTime(s.updated_at)}</span>
                </div>
              )}
            </div>
            {renamingId !== s.id && (
              <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                <button
                  onClick={(e) => { e.stopPropagation(); handleRenameStart(s.id, s.name) }}
                  className="p-0.5 text-cb-muted hover:text-cb-neon rounded transition-colors"
                  title="Rename"
                >
                  <Pencil size={11} />
                </button>
                <button
                  onClick={(e) => handleDelete(s.id, e)}
                  className="p-0.5 text-cb-muted hover:text-cb-red rounded transition-colors"
                  title="Delete"
                >
                  <Trash2 size={11} />
                </button>
              </div>
            )}
          </div>
        ))}
        {sessions.length === 0 && (
          <div className="px-3 py-4 text-xs text-cb-muted/40 text-center font-mono">No sessions yet</div>
        )}
      </div>
    </div>
  )
}
