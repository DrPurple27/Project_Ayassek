import { MessageSquare, Brain, Database, Settings } from 'lucide-react'

type Panel = 'chat' | 'nrs' | 'rag' | 'settings'

interface SidebarProps {
  activePanel: Panel
  onPanelChange: (panel: Panel) => void
}

const ITEMS: { id: Panel; icon: typeof MessageSquare; label: string }[] = [
  { id: 'chat', icon: MessageSquare, label: 'Chat' },
  { id: 'nrs', icon: Brain, label: 'NRS' },
  { id: 'rag', icon: Database, label: 'RAG' },
  { id: 'settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar({ activePanel, onPanelChange }: SidebarProps) {
  return (
    <aside className="w-16 lg:w-64 bg-cb-surface border-r border-cb-border flex flex-col shrink-0 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-cb-neon/5 via-transparent to-cb-cyan/3 pointer-events-none" />

      <div className="relative p-4 border-b border-cb-border">
        <h2 className="hidden lg:block text-sm font-bold text-cb-neon tracking-[0.25em] uppercase cb-text-glow">
          Ayassek
        </h2>
        <span className="lg:hidden text-sm font-bold text-cb-neon cb-text-glow">A</span>
      </div>

      <nav className="relative flex-1 py-2">
        {ITEMS.map(({ id, icon: Icon, label }) => {
          const isActive = activePanel === id
          return (
            <button
              key={id}
              onClick={() => onPanelChange(id)}
              aria-label={label}
              title={label}
              className={`relative w-full flex items-center gap-3 px-4 py-3 text-sm transition-all duration-300 ${
                isActive
                  ? 'text-cb-neon bg-cb-neon/10'
                  : 'text-cb-muted hover:text-cb-text hover:bg-cb-card-hover'
              }`}
            >
              {isActive && (
                <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-cb-neon shadow-neon" />
              )}
              <Icon size={20} className={`shrink-0 ${isActive ? 'drop-shadow-[0_0_6px_rgba(140,82,255,0.5)]' : ''}`} />
              <span className="hidden lg:inline tracking-wide">{label}</span>
            </button>
          )
        })}
      </nav>

      <div className="relative p-4 border-t border-cb-border">
        <div className="hidden lg:block text-[10px] text-cb-muted font-mono uppercase tracking-widest">v0.1.0</div>
      </div>
    </aside>
  )
}
