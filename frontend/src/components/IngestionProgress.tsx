import { useEffect, useState } from 'react'
import { FileText, Clock, HardDrive, CheckCircle2, AlertCircle } from 'lucide-react'
import type { IngestTaskStatus } from '@/api/client'

interface Props {
  task: IngestTaskStatus | null
  onClose?: () => void
}

const stageLabels: Record<string, string> = {
  pending: 'Queued',
  detecting: 'Detecting PDF type',
  digital: 'Processing digital PDF',
  ocr: 'Running OCR',
  chunking: 'Chunking text',
  embedding: 'Generating embeddings',
  storing: 'Storing vectors',
  completed: 'Completed',
  failed: 'Failed',
}

export default function IngestionProgress({ task, onClose }: Props) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!task) return
    const start = new Date(task.created_at).getTime()
    const timer = setInterval(() => {
      setElapsed(Date.now() - start)
    }, 1000)
    return () => clearInterval(timer)
  }, [task?.created_at, task])

  if (!task) return null

  const formatTime = (ms: number) => {
    const s = Math.floor(ms / 1000)
    const m = Math.floor(s / 60)
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-cb-bg/70 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-cb-card border border-cb-neon/20 rounded-xl w-full max-w-md mx-4 shadow-neon"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-cb-border">
          <div className="flex items-center gap-3">
            <FileText size={22} className="text-cb-cyan" />
            <div>
              <h2 className="text-sm font-semibold text-cb-text-bright cb-text-glow">Ingesting Document</h2>
              <p className="text-[11px] text-cb-muted font-mono">Task {task.task_id.slice(0, 8)}</p>
            </div>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-cb-muted hover:text-cb-cyan transition-colors">
              &#x2715;
            </button>
          )}
        </div>

        <div className="p-5 space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-cb-muted uppercase tracking-wider font-mono">{stageLabels[task.current_stage] || task.current_stage}</span>
              <span className="font-mono text-cb-cyan">
                {(task.progress * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-2 bg-cb-border rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  task.status === 'failed' ? 'bg-cb-red shadow-red' : 'bg-cb-neon shadow-neon-sm'
                }`}
                style={{ width: `${task.progress * 100}%` }}
              />
            </div>
          </div>

          {task.total_pages > 0 && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-cb-muted uppercase tracking-wider font-mono">Pages processed</span>
                <span className="font-mono text-cb-text-bright">
                  {task.current_page} / {task.total_pages}
                </span>
              </div>
              <div className="h-1.5 bg-cb-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-cb-gold"
                  style={{ width: `${(task.current_page / task.total_pages) * 100}%` }}
                />
              </div>
            </div>
          )}

          {task.error && (
            <div className="bg-cb-red/10 border border-cb-red/30 rounded-lg p-3 text-sm text-cb-red">
              <div className="flex items-center gap-2">
                <AlertCircle size={16} />
                <span>Error: {task.error}</span>
              </div>
            </div>
          )}

          {task.status === 'completed' && task.result && (
            <div className="bg-cb-bg border border-cb-border rounded-lg p-3 space-y-2">
              <p className="text-xs font-medium text-cb-muted uppercase tracking-wider font-mono">Result</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-1 text-cb-muted">
                  <CheckCircle2 size={12} className="text-cb-green" />
                  <span>Chunks: {task.result.chunks_created}</span>
                </div>
                <div className="flex items-center gap-1 text-cb-muted">
                  <HardDrive size={12} className="text-cb-cyan" />
                  <span>Vectors: {task.result.vectors_stored}</span>
                </div>
                {task.result.errors && task.result.errors.length > 0 && (
                  <div className="col-span-2 flex items-center gap-1 text-cb-gold">
                    <Clock size={12} />
                    <span>Warnings: {task.result.errors.length}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between text-[11px] text-cb-muted pt-2 border-t border-cb-border font-mono">
            <span>Elapsed</span>
            <span>{formatTime(elapsed)}</span>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-cb-border flex justify-end gap-2">
          {onClose && (
            <button
              onClick={onClose}
              disabled={task.status === 'running'}
              className="px-4 py-2 text-sm bg-cb-border hover:bg-cb-border-light disabled:opacity-50 text-cb-text rounded-lg transition-colors"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
