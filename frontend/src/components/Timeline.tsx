import { BrainFact } from '@/api/client'

interface TimelineEntry {
  date: string
  type: 'created' | 'updated' | 'status_change' | 'version'
  factId: string
  text: string
  status: string
}

interface Props {
  facts: BrainFact[]
}

export default function Timeline({ facts }: Props) {
  const entries: TimelineEntry[] = facts.flatMap((f) => {
    const out: TimelineEntry[] = []
    out.push({
      date: f.timestamp,
      type: 'created',
      factId: f.id,
      text: f.text,
      status: f.status,
    })
    if (f.version_history) {
      f.version_history.forEach((v) => {
        out.push({
          date: v.timestamp,
          type: 'version',
          factId: f.id,
          text: v.text,
          status: v.status,
        })
      })
    }
    return out
  }).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

  if (entries.length === 0) return null

  const formatDate = (d: string) => {
    const date = new Date(d)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const grouped = entries.reduce<Record<string, TimelineEntry[]>>((acc, entry) => {
    const key = formatDate(entry.date)
    if (!acc[key]) acc[key] = []
    acc[key].push(entry)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-cb-muted uppercase tracking-wider font-mono">Timeline</h3>
      <div className="relative">
        <div className="absolute left-[7px] top-2 bottom-2 w-0.5 bg-cb-border" />
        {Object.entries(grouped).map(([dateLabel, items]) => (
          <div key={dateLabel} className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-[15px] h-[15px] rounded-full bg-cb-neon border-2 border-cb-bg z-10 shrink-0 shadow-neon-sm" />
              <span className="text-xs text-cb-muted font-medium font-mono">{dateLabel}</span>
            </div>
            <div className="ml-6 space-y-2">
              {items.map((entry, i) => (
                <div key={`${entry.factId}-${i}`} className="bg-cb-card border border-cb-border rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] text-cb-muted uppercase font-mono">
                      {entry.type === 'created' ? 'Created' : entry.type === 'version' ? 'Updated' : entry.type}
                    </span>
                    <span className={`text-[10px] px-1 rounded border ${
                      entry.status === 'active' ? 'bg-cb-neon/15 text-cb-neon border-cb-neon/30'
                        : entry.status === 'superseded' ? 'bg-cb-gold/15 text-cb-gold border-cb-gold/30'
                        : entry.status === 'contradicted' ? 'bg-cb-red/15 text-cb-red border-cb-red/30'
                        : 'bg-cb-muted/15 text-cb-muted border-cb-border'
                    }`}>
                      {entry.status}
                    </span>
                  </div>
                  <p className="text-xs text-cb-text leading-relaxed line-clamp-2">{entry.text}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
