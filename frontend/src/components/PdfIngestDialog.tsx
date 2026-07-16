import { useState, useRef, useCallback } from 'react'
import { Upload, Check } from 'lucide-react'
import IngestionProgress from '@/components/IngestionProgress'
import { useRagStore } from '@/store/rag'

interface Props {
  open: boolean
  onClose: () => void
  onTaskCreated?: (taskId: string) => void
}

const MAX_FILE_SIZE = 1024 * 1024 * 1024
const ACCEPTED_TYPES = ['application/pdf']

export default function PdfIngestDialog({ open, onClose, onTaskCreated }: Props) {
  const { ingestFile, pollTask, loading } = useRagStore()
  const [file, setFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [category, setCategory] = useState('upload')
  const [tags, setTags] = useState('')
  const [status, setStatus] = useState<'idle' | 'uploading' | 'polling' | 'done' | 'error'>('idle')
  const [taskId, setTaskId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleFile = (f: File) => {
    if (!ACCEPTED_TYPES.includes(f.type)) {
      setError('Only PDF files are supported')
      return
    }
    if (f.size > MAX_FILE_SIZE) {
      setError('File size must be less than 1GB')
      return
    }
    setFile(f)
    setError(null)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }, [])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  const handleSubmit = async () => {
    if (!file) return
    setStatus('uploading')
    setError(null)

    try {
      const taskId = await ingestFile(file, category, tags.split(',').map(t => t.trim()).filter(Boolean))
      setTaskId(taskId)
      setStatus('polling')
      onTaskCreated?.(taskId)
      await pollTask(taskId)
      setStatus('done')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setStatus('error')
    }
  }

  const reset = () => {
    setFile(null)
    setStatus('idle')
    setError(null)
    setTaskId(null)
    setTags('')
    setCategory('upload')
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-cb-bg/70 backdrop-blur-sm" onClick={() => { reset(); onClose() }}>
      <div
        className="bg-cb-card border border-cb-neon/20 rounded-xl w-full max-w-md mx-4 shadow-neon"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-cb-border">
          <h2 className="text-sm font-semibold text-cb-text-bright cb-text-glow">Ingest PDF</h2>
          <button onClick={() => { reset(); onClose() }} className="text-cb-muted hover:text-cb-cyan transition-colors">&#x2715;</button>
        </div>

        <div className="p-5 space-y-4">
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`relative border-2 border-dashed rounded-lg p-6 text-center transition-all ${
              dragActive
                ? 'border-cb-cyan bg-cb-cyan/10 shadow-cyan-sm'
                : file
                  ? 'border-cb-green bg-cb-green/10 shadow-green'
                  : 'border-cb-border hover:border-cb-neon/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            />

            {file ? (
              <div className="flex items-center gap-3 p-3 bg-cb-bg border border-cb-border rounded-lg">
                <Check size={20} className="text-cb-green" />
                <div className="flex-1 text-left min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-cb-muted font-mono">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
                </div>
                <button
                  onClick={() => setFile(null)}
                  className="text-cb-muted hover:text-cb-red transition-colors"
                >
                  &#x2715;
                </button>
              </div>
            ) : (
              <>
                <Upload size={32} className="mx-auto text-cb-muted" />
                <p className="mt-3 text-sm text-cb-muted">Drag & drop a PDF, or click to browse</p>
                <p className="text-xs text-cb-muted/40 mt-1 font-mono">Max 1GB &#x2022; Auto-detects digital vs scanned</p>
              </>
            )}
          </div>

          {error && (
            <div className="bg-cb-red/10 border border-cb-red/30 rounded-lg p-3 text-sm text-cb-red">
              <div className="flex items-center gap-2">
                <span>&#x26A0;</span>
                <span>{error}</span>
              </div>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs text-cb-muted mb-1 uppercase tracking-wider font-mono">Category</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="cb-input w-full"
              >
                <option value="upload">Upload</option>
                <option value="reference">Reference</option>
                <option value="project">Project</option>
              </select>
            </div>

            <div>
              <label className="block text-xs text-cb-muted mb-1 uppercase tracking-wider font-mono">Tags (comma-separated)</label>
              <input
                value={tags}
                onChange={e => setTags(e.target.value)}
                placeholder="technical, documentation, scanned"
                className="cb-input w-full"
              />
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              onClick={() => { reset(); onClose() }}
              disabled={status === 'polling'}
              className="flex-1 px-3 py-2 text-sm text-cb-muted hover:text-cb-text-bright rounded-lg disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!file || status === 'polling' || loading}
              className="flex-1 cb-btn-neon py-2 text-sm disabled:opacity-30"
            >
              {status === 'uploading' ? 'Uploading...' : 'Upload & Ingest'}
            </button>
          </div>
        </div>
      </div>

      <IngestionProgress
        task={taskId ? { 
          task_id: taskId, 
          status: 'running' as const, 
          progress: 0, 
          current_stage: '', 
          current_page: 0, 
          total_pages: 0, 
          created_at: new Date().toISOString(), 
          updated_at: new Date().toISOString() 
        } : null}
        onClose={() => {}}
      />
    </div>
  )
}
