import { useState, lazy, Suspense } from 'react'
import Sidebar from '@/components/Sidebar'
import ChatPanel from '@/panels/ChatPanel'
import RagPanel from '@/panels/RagPanel'
import SettingsPanel from '@/panels/SettingsPanel'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { WebSocketProvider, useWs } from '@/contexts/WebSocketProvider'

const NRSPanel = lazy(() => import('@/panels/NRSPanel'))

type Panel = 'chat' | 'nrs' | 'rag' | 'settings'

const PANEL_LABELS: Record<Panel, string> = {
  chat: 'Chat',
  nrs: 'NRS — Neural Recall System',
  rag: 'RAG Pipeline',
  settings: 'Settings',
}

function AppContent() {
  const [activePanel, setActivePanel] = useState<Panel>('chat')
  const { isConnected, isReconnecting } = useWs()

  return (
    <div className="flex h-screen bg-cb-bg text-cb-text cb-grid-bg">
      <Sidebar activePanel={activePanel} onPanelChange={setActivePanel} />

      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="relative flex items-center justify-between px-6 py-3 border-b border-cb-border bg-cb-surface/80 backdrop-blur-sm shrink-0 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-cb-neon/5 via-transparent to-cb-cyan/5 pointer-events-none" />
          <h1 className="relative text-lg font-semibold text-cb-text-bright cb-text-glow tracking-wide">
            {PANEL_LABELS[activePanel]}
          </h1>
          <div className="relative flex items-center gap-3">
            <span className={`flex items-center gap-1.5 text-xs font-mono ${
              isReconnecting ? 'text-cb-gold' : isConnected ? 'text-cb-green' : 'text-cb-red'
            }`}>
              <span className={`w-2 h-2 rounded-full ${
                isReconnecting
                  ? 'bg-cb-gold shadow-gold animate-glow-pulse'
                  : isConnected
                    ? 'bg-cb-green shadow-green'
                    : 'bg-cb-red shadow-red animate-glow-pulse'
              }`} />
              <span className="uppercase tracking-widest text-[10px]">
                {isReconnecting ? 'Reconnecting' : isConnected ? 'Online' : 'Offline'}
              </span>
            </span>
          </div>
        </header>

        <div className="flex-1 overflow-auto relative">
          <div className="absolute inset-0 pointer-events-none z-50 cb-scanline opacity-30" />
          <div key={activePanel} className="animate-fade-in h-full">
            {activePanel === 'chat' && (
              <ErrorBoundary>
                <ChatPanel />
              </ErrorBoundary>
            )}
            {activePanel === 'nrs' && (
              <ErrorBoundary>
                <Suspense fallback={<div className="flex items-center justify-center h-full text-cb-muted"><div className="text-center"><div className="w-8 h-8 border-4 border-cb-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" /><p className="text-cb-muted text-sm">Loading Neural Graph...</p></div></div>}>
                  <NRSPanel />
                </Suspense>
              </ErrorBoundary>
            )}
            {activePanel === 'rag' && (
              <ErrorBoundary>
                <RagPanel />
              </ErrorBoundary>
            )}
            {activePanel === 'settings' && (
              <ErrorBoundary>
                <SettingsPanel />
              </ErrorBoundary>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

function App() {
  return (
    <WebSocketProvider>
      <AppContent />
    </WebSocketProvider>
  )
}

export default App
