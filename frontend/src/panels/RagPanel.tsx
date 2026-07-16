import { useEffect, useState, useRef } from 'react'
import { Upload, Plus, FileText, Trash2, RefreshCw, Loader2, RotateCcw } from 'lucide-react'
import { api } from '@/api/client'
import { useRagStore } from '@/store/rag'
import PdfIngestDialog from '@/components/PdfIngestDialog'
import IngestionProgress from '@/components/IngestionProgress'
import QueryTester from '@/components/QueryTester'
import RagStatusCard from '@/components/RagStatusCard'

export default function RagPanel() {
  const {
    ingestTask,
    loading,
    fetchStatus,
    ingest,
    ingestFile,
    pollTask,
    deleteSource,
    deleteCategory,
    wipeAll,
  } = useRagStore()

  const [ingestText, setIngestText] = useState('')
  const [ingestSource, setIngestSource] = useState('manual')
  const [showPdfDialog, setShowPdfDialog] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [deleteSourceValue, setDeleteSourceValue] = useState('')
  const [deleteCategoryValue, setDeleteCategoryValue] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  // Poll active task
  useEffect(() => {
    if (activeTaskId) {
      pollTask(activeTaskId).then(() => setActiveTaskId(null))
    }
  }, [activeTaskId, pollTask])

  const handleIngest = () => {
    if (!ingestText.trim()) return
    ingest(ingestText.trim(), ingestSource || 'manual')
    setIngestText('')
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const taskId = await ingestFile(file)
      if (taskId) setActiveTaskId(taskId)
    } catch (err: unknown) {
      console.error('File upload failed:', err instanceof Error ? err.message : err)
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDeleteSource = async () => {
    if (!deleteSourceValue.trim()) return
    await deleteSource(deleteSourceValue.trim())
    setDeleteSourceValue('')
    fetchStatus()
  }

  const handleDeleteCategory = async () => {
    if (!deleteCategoryValue.trim()) return
    await deleteCategory(deleteCategoryValue.trim())
    setDeleteCategoryValue('')
    fetchStatus()
  }

  const handleReindex = async () => {
    await api.ragReindex()
    fetchStatus()
  }

  const activeTask = ingestTask && ingestTask.task_id === activeTaskId ? ingestTask : null

  return (
    <div className="max-w-4xl mx-auto w-full p-4 space-y-6">
      <RagStatusCard />

      <QueryTester />

      {/* Ingestion Controls */}
      <div className="cb-panel rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium flex items-center gap-2 text-cb-text-bright">
            <Upload size={16} className="text-cb-cyan" />
            Ingestion
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleReindex}
              disabled={loading}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs cb-btn-cyan rounded-lg disabled:opacity-30"
              title="Re-index all vectors"
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Re-index
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs cb-btn-neon rounded-lg disabled:opacity-30"
            >
              <FileText size={12} /> Upload File
            </button>
            <button
              onClick={() => setShowPdfDialog(true)}
              className="flex items-center gap-1 px-2.5 py-1.5 text-xs cb-btn-gold rounded-lg"
            >
              <Plus size={12} /> PDF
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.json,.csv,.py,.js,.ts,.html,.css"
          className="hidden"
          onChange={handleFileUpload}
        />

        {/* Text ingestion */}
        <div className="mb-4 p-3 bg-cb-bg border border-cb-border rounded-lg space-y-2">
          <label className="text-xs text-cb-muted uppercase tracking-wider font-mono">Text Ingestion</label>
          <textarea
            value={ingestText}
            onChange={e => setIngestText(e.target.value)}
            placeholder="Paste text to ingest..."
            rows={3}
            className="cb-input w-full resize-none"
          />
          <div className="flex gap-2">
            <input
              value={ingestSource}
              onChange={e => setIngestSource(e.target.value)}
              placeholder="source name"
              className="cb-input flex-1 text-xs"
            />
            <button
              onClick={handleIngest}
              disabled={!ingestText.trim() || loading}
              className="cb-btn-green px-3 py-2 text-sm disabled:opacity-30"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : 'Ingest Text'}
            </button>
          </div>
        </div>

        {/* Delete controls */}
        <div className="border-t border-cb-border pt-4 space-y-3">
          <p className="text-xs text-cb-muted uppercase tracking-wider font-mono">Delete Data</p>
          <div className="flex gap-2">
            <input
              value={deleteSourceValue}
              onChange={e => setDeleteSourceValue(e.target.value)}
              placeholder="source path to delete"
              className="cb-input flex-1 text-xs"
            />
            <button
              onClick={handleDeleteSource}
              disabled={!deleteSourceValue.trim() || loading}
              className="flex items-center gap-1 cb-btn-red px-3 py-1.5 text-sm disabled:opacity-30"
            >
              <Trash2 size={12} /> Delete Source
            </button>
          </div>
          <div className="flex gap-2">
            <input
              value={deleteCategoryValue}
              onChange={e => setDeleteCategoryValue(e.target.value)}
              placeholder="category to delete"
              className="cb-input flex-1 text-xs"
            />
            <button
              onClick={handleDeleteCategory}
              disabled={!deleteCategoryValue.trim() || loading}
              className="flex items-center gap-1 cb-btn-red px-3 py-1.5 text-sm disabled:opacity-30"
            >
              <Trash2 size={12} /> Delete Category
            </button>
          </div>
          <button
            onClick={() => {
              if (confirm("Wipe ALL RAG data (documents, vectors, index)? This cannot be undone.")) {
                wipeAll()
              }
            }}
            disabled={loading}
            className="flex items-center gap-1 cb-btn-red px-3 py-1.5 text-sm w-full justify-center disabled:opacity-30"
          >
            <RotateCcw size={12} /> Wipe All RAG Data
          </button>
        </div>
      </div>

      {/* Active task progress */}
      {activeTask && (
        <IngestionProgress task={activeTask} onClose={() => setActiveTaskId(null)} />
      )}

      {showPdfDialog && (
        <PdfIngestDialog
          open={showPdfDialog}
          onClose={() => setShowPdfDialog(false)}
          onTaskCreated={(taskId) => { setActiveTaskId(taskId); setShowPdfDialog(false) }}
        />
      )}
    </div>
  )
}
