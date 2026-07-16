import { useEffect, useRef, useCallback, useState } from 'react'

export interface WSMessage {
  type: string
  data: any
  session_id?: string
  timestamp?: string
}

interface UseWebSocketOptions {
  sessionId?: string
  onMessage: (msg: WSMessage) => void
  onReconnect?: () => void
  maxRetries?: number
}

export function useWebSocket({ sessionId, onMessage, maxRetries = 5 }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isReconnecting, setIsReconnecting] = useState(false)

  const connectRef = useRef<(() => void) | null>(null)

  const connect = useCallback(() => {
    const wsUrl = sessionId
      ? `ws://${window.location.host}/ws/${sessionId}`
      : `ws://${window.location.host}/ws`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setIsConnected(true)
      setIsReconnecting(false)
      retryCountRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data)
        onMessage(msg)
      } catch {
        // ignore non-JSON messages
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      if (retryCountRef.current < maxRetries) {
        setIsReconnecting(true)
        retryTimerRef.current = setTimeout(() => {
          retryCountRef.current++
          connectRef.current?.()
        }, 3000)
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [sessionId, onMessage, maxRetries])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    connect()
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  return { isConnected, isReconnecting, send }
}
