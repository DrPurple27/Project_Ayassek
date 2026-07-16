import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { FileText } from 'lucide-react'

interface FactNodeData {
  label: string
  category?: string
  type?: string
  summary?: string
  importance?: number
  tags?: string[]
  [key: string]: unknown
}

function FactNode({ data: raw, selected }: NodeProps) {
  const data = raw as unknown as FactNodeData

  return (
    <div
      className={`rounded-lg border-2 border-dashed px-3 py-2 min-w-[140px] transition-shadow ${
        selected ? 'shadow-[0_0_15px_rgba(255,170,0,0.3)]' : 'shadow-[0_0_6px_rgba(0,0,0,0.4)]'
      }`}
      style={{
        background: 'linear-gradient(135deg, #0f0f1a 0%, #1a1425 100%)',
        borderColor: selected ? '#ffaa00' : '#2a2a40',
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#ffaa00] !w-2 !h-2" style={{ boxShadow: '0 0 6px rgba(255,170,0,0.4)' }} />
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-[#ffaa00]" style={{ filter: 'drop-shadow(0 0 4px rgba(255,170,0,0.4))' }}><FileText size={12} /></span>
        <span className="text-[10px] font-semibold text-[#ffaa00] uppercase tracking-widest font-mono">Fact</span>
      </div>
      <p className="text-xs text-[#e8e8ff] leading-snug line-clamp-3 mb-1">
        {data.label}
      </p>
      {data.tags && data.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {data.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="text-[9px] px-1.5 py-0.5 rounded bg-[#ffaa00]/10 text-[#ffaa00] border border-[#ffaa00]/20"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      {data.importance != null && (
        <div className="mt-1.5 flex items-center gap-1">
          <div className="h-1 flex-1 rounded-full bg-[#1a1a2e] overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(100, Math.max(0, data.importance))}%`,
                background: '#ffaa00',
                boxShadow: '0 0 6px rgba(255,170,0,0.3)',
              }}
            />
          </div>
          <span className="text-[8px] text-[#5a5a7a] font-mono">{data.importance}%</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-[#ffaa00] !w-2 !h-2" style={{ boxShadow: '0 0 6px rgba(255,170,0,0.4)' }} />
    </div>
  )
}

export default memo(FactNode)
