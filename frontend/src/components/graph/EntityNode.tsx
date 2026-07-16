import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Brain, FileText } from 'lucide-react'

interface EntityNodeData {
  label: string
  category?: string
  type?: string
  summary?: string
  importance?: number
  [key: string]: unknown
}

const CATEGORY_COLORS: Record<string, string> = {
  projects: '#8C52FF',
  people: '#00ff88',
  concepts: '#ffaa00',
  meetings: '#ff2d7b',
  references: '#00f0ff',
  tasks: '#ff3355',
  default: '#5a5a7a',
}

function EntityNode({ data: raw, selected }: NodeProps) {
  const data = raw as unknown as EntityNodeData
  const category = data.category || 'default'
  const color = CATEGORY_COLORS[category] || CATEGORY_COLORS.default
  const Icon = data.type === 'fact' ? FileText : Brain

  return (
    <div
      className={`rounded-xl border-2 px-4 py-3 min-w-[160px] transition-shadow ${
        selected ? 'shadow-[0_0_20px_rgba(140,82,255,0.4)]' : 'shadow-[0_0_8px_rgba(0,0,0,0.5)]'
      }`}
      style={{
        background: 'linear-gradient(135deg, #0f0f1a 0%, #141425 100%)',
        borderColor: selected ? '#8C52FF' : color,
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#8C52FF] !w-2 !h-2" style={{ boxShadow: '0 0 6px rgba(140,82,255,0.5)' }} />
      <div className="flex items-center gap-2 mb-1">
        <span style={{ color, filter: `drop-shadow(0 0 4px ${color}40)` }}><Icon size={14} /></span>
        <span className="text-xs font-semibold text-[#e8e8ff] truncate max-w-[120px]">
          {data.label}
        </span>
      </div>
      {data.summary && (
        <p className="text-[10px] text-[#5a5a7a] leading-relaxed line-clamp-2">
          {data.summary}
        </p>
      )}
      {data.importance != null && (
        <div className="mt-1 flex items-center gap-1">
          <div className="h-1 flex-1 rounded-full bg-[#1a1a2e] overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${Math.min(100, Math.max(0, data.importance))}%`,
                background: data.importance > 70 ? '#00ff88' : data.importance > 40 ? '#ffaa00' : '#5a5a7a',
                boxShadow: `0 0 6px ${data.importance > 70 ? 'rgba(0,255,136,0.3)' : data.importance > 40 ? 'rgba(255,170,0,0.3)' : 'transparent'}`,
              }}
            />
          </div>
          <span className="text-[9px] text-[#5a5a7a] font-mono">{data.importance}%</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-[#8C52FF] !w-2 !h-2" style={{ boxShadow: '0 0 6px rgba(140,82,255,0.5)' }} />
    </div>
  )
}

export default memo(EntityNode)
