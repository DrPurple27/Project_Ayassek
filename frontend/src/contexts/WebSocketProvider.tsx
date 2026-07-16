import { createContext, useContext, useCallback, type ReactNode } from 'react'
import { useWebSocket, type WSMessage } from '@/hooks/useWebSocket'
import { useSecondBrainStore } from '@/store/secondBrain'
import { useChatStore } from '@/store/chat'

interface WebSocketContextValue {
  isConnected: boolean
  isReconnecting: boolean
  lastEvent: WSMessage | null
  send: (data: object) => void
}

const WebSocketContext = createContext<WebSocketContextValue>({
  isConnected: false,
  isReconnecting: false,
  lastEvent: null,
  send: () => {},
})

export function useWs() {
  return useContext(WebSocketContext)
}

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const fetchEntities = useSecondBrainStore((s) => s.fetchEntities)
  const fetchStats = useSecondBrainStore((s) => s.fetchStats)
  const addMessage = useChatStore((s) => s.addMessage)
  const addAssistantResponse = useChatStore((s) => s.addAssistantResponse)
  const setStreamingContent = useChatStore((s) => s.setStreamingContent)
  const addToolCall = useChatStore((s) => s.addToolCall)
  const updateToolCall = useChatStore((s) => s.updateToolCall)
  const sessionId = useChatStore((s) => s.sessionId)

  const handleMessage = useCallback((msg: WSMessage) => {
    switch (msg.type) {
      case 'memory.updated':
        fetchEntities()
        fetchStats()
        break

      case 'brain.token': {
        const hasStreaming = useChatStore.getState().messages.some((m) => m.isStreaming)
        if (!hasStreaming) {
          addMessage({
            role: 'assistant',
            content: '',
            timestamp: Date.now(),
            isStreaming: true,
          })
        }
        setStreamingContent(msg.data?.text || '')
        break
      }

      case 'brain.tool_call':
        addToolCall({
          name: msg.data?.tool || 'unknown',
          args: JSON.stringify(msg.data?.args || {}),
          status: 'running',
        })
        break

      case 'brain.tool_result':
        updateToolCall(
          msg.data?.tool || 'unknown',
          msg.data?.result || '',
          'complete'
        )
        break

      case 'brain.error':
        addAssistantResponse(`\n\n**Error:** ${msg.data?.error || 'Unknown error'}`)
        break

      case 'brain.response':
        if (msg.data?.text) {
          addAssistantResponse(msg.data.text)
        }
        break

      case 'brain.thinking':
      case 'brain.done':
      case 'system.status':
        break

      default:
        break
    }
  }, [fetchEntities, fetchStats, addMessage, addAssistantResponse, setStreamingContent, addToolCall, updateToolCall])

  const { isConnected, isReconnecting, send } = useWebSocket({
    sessionId: sessionId ?? undefined,
    onMessage: handleMessage,
  })

  return (
    <WebSocketContext.Provider value={{ isConnected, isReconnecting, lastEvent: null, send }}>
      {children}
    </WebSocketContext.Provider>
  )
}