import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Trash2, AtSign, Brain, Image, X, ChevronDown, ChevronRight, CheckCircle, Loader2, AlertCircle, Mic, Square, Pencil, Download, Copy, HelpCircle, Volume2, VolumeX } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { useChatStore } from '@/store/chat'
import { useSecondBrainStore } from '@/store/secondBrain'
import { useAudioRecorder } from '@/hooks/useAudioRecorder'
import SessionSidebar from '@/components/SessionSidebar'
import { useWs } from '@/contexts/WebSocketProvider'
import ModelSelector from '@/components/ModelSelector'

const now = () => Date.now()

const KEYBOARD_SHORTCUTS = [
  { key: 'Enter', action: 'Send message' },
  { key: 'Shift+Enter', action: 'New line' },
  { key: '@', action: 'Mention entity' },
  { key: 'Ctrl+Shift+/', action: 'Show shortcuts' },
  { key: 'Ctrl+Shift+K', action: 'Search entities (NRS panel)' },
  { key: '↑/↓', action: 'Navigate mentions' },
  { key: 'Esc', action: 'Close dropdowns/cancel' },
]

function ToolCallCard({ call }: { call: { name: string; args: string; result?: string; status: string } }) {
  const [expanded, setExpanded] = useState(false)
  const isRunning = call.status === 'running'
  const isError = call.status === 'error'

  return (
    <div
      className={`rounded-lg border px-3 py-2 my-1 text-xs backdrop-blur-sm ${
        isRunning
          ? 'border-cb-gold/30 bg-cb-gold/10'
          : isError
          ? 'border-cb-red/30 bg-cb-red/10'
          : 'border-cb-border bg-cb-surface'
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left"
      >
        {isRunning ? (
          <Loader2 size={12} className="animate-spin text-cb-gold" />
        ) : isError ? (
          <AlertCircle size={12} className="text-cb-red" />
        ) : (
          <CheckCircle size={12} className="text-cb-green" />
        )}
        <code className="text-cb-cyan text-xs font-mono">{call.name}</code>
        <span className="flex-1" />
        {expanded ? <ChevronDown size={12} className="text-cb-muted" /> : <ChevronRight size={12} className="text-cb-muted" />}
      </button>
      {expanded && (
        <div className="mt-2 space-y-1">
          <div className="text-cb-muted">Args:</div>
          <pre className="text-cb-text font-mono text-[10px] bg-cb-bg rounded p-1.5 overflow-x-auto whitespace-pre-wrap break-all max-w-full max-h-48 overflow-y-auto">
            {call.args}
          </pre>
          {call.result && (
            <>
              <div className="text-cb-muted">Result:</div>
              <pre className="text-cb-text font-mono text-[10px] bg-cb-bg rounded p-1.5 overflow-x-auto whitespace-pre-wrap break-all max-w-full max-h-48 overflow-y-auto">
                {call.result.slice(0, 1000)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ImagePreview({ src, onRemove }: { src: string; onRemove?: () => void }) {
  return (
    <div className="relative inline-block group">
      <img src={src} alt="Upload preview" className="max-h-32 rounded-lg border border-cb-border" />
      {onRemove && (
        <button
          onClick={onRemove}
          className="absolute -top-1.5 -right-1.5 bg-cb-red rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-red"
        >
          <X size={12} />
        </button>
      )}
    </div>
  )
}

export default function ChatPanel() {
  const {
    messages,
    sessionId,
    isStreaming,
    streamingContent,
    streamingToolCalls,
    addMessage,
    setStreaming,
    clear,
    fetchSessions,
    updateMessage,
    exportMarkdown,
    exportJSON,
  } = useChatStore()
  const { entities, fetchEntities } = useSecondBrainStore()
  const { send: wsSend } = useWs()
  const [input, setInput] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const [mentionIndex, setMentionIndex] = useState(0)
  const [showContext, setShowContext] = useState(true)
  const [images, setImages] = useState<string[]>([])
  const [showSessionSidebar, setShowSessionSidebar] = useState(true)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editValue, setEditValue] = useState('')
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(false)
  const [transcribedText, setTranscribedText] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const {
    isRecording,
    duration,
    transcribing,
    startRecording,
    stopRecording,
    transcribeAudio,
  } = useAudioRecorder()

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleGlobalKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === '/' && e.ctrlKey && e.shiftKey) {
      e.preventDefault()
      setShowShortcuts(!showShortcuts)
    }
  }, [showShortcuts])

  useEffect(() => {
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [handleGlobalKeyDown])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  useEffect(() => {
    fetchEntities()
    fetchSessions()
  }, [fetchEntities, fetchSessions])

  const filteredMentions = entities.filter((e) =>
    e.name.toLowerCase().includes(mentionQuery.toLowerCase())
  )

  const handleInputChange = useCallback((value: string) => {
    setInput(value)
    const cursorPos = inputRef.current?.selectionStart ?? value.length
    const textBefore = value.slice(0, cursorPos)
    const atMatch = textBefore.match(/@(\w*)$/)
    if (atMatch) {
      setMentionQuery(atMatch[1])
      setShowMentions(true)
      setMentionIndex(0)
    } else {
      setShowMentions(false)
    }
  }, [])

  const insertMention = (name: string) => {
    const cursorPos = inputRef.current?.selectionStart ?? input.length
    const textBefore = input.slice(0, cursorPos)
    const textAfter = input.slice(cursorPos)
    const atIndex = textBefore.lastIndexOf('@')
    const newText = textBefore.slice(0, atIndex) + `@${name} ` + textAfter
    setInput(newText)
    setShowMentions(false)
    inputRef.current?.focus()
  }

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    for (const file of Array.from(files)) {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const dataUrl = ev.target?.result as string
        if (dataUrl) setImages((prev) => [...prev, dataUrl])
      }
      reader.readAsDataURL(file)
    }
  }

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          const reader = new FileReader()
          reader.onload = (ev) => {
            const dataUrl = ev.target?.result as string
            if (dataUrl) setImages((prev) => [...prev, dataUrl])
          }
          reader.readAsDataURL(file)
        }
      }
    }
  }, [])

  const handleSend = () => {
    const text = input.trim()
    if ((!text && images.length === 0) || isStreaming) return
    setInput('')
    const currentImages = [...images]
    setImages([])
    addMessage({ role: 'user', content: text || '[Image]', timestamp: now(), images: currentImages })
    setStreaming(true)

    wsSend({
      type: 'chat',
      message: text,
      session_id: sessionId,
      images: currentImages.length > 0 ? currentImages : undefined,
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (showMentions) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setMentionIndex((i) => Math.min(i + 1, filteredMentions.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setMentionIndex((i) => Math.max(i - 1, 0))
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        if (filteredMentions[mentionIndex]) {
          insertMention(filteredMentions[mentionIndex].name)
        }
        return
      }
      if (e.key === 'Escape') {
        setShowMentions(false)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleEditStart = (index: number, content: string) => {
    setEditingIndex(index)
    setEditValue(content)
  }

  const handleEditConfirm = () => {
    if (editingIndex !== null && editValue.trim()) {
      updateMessage(editingIndex, editValue.trim())
    }
    setEditingIndex(null)
  }

  const handleExport = (format: 'md' | 'json') => {
    const content = format === 'md' ? exportMarkdown() : exportJSON()
    const blob = new Blob([content], { type: format === 'md' ? 'text/markdown' : 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chat-export.${format}`
    a.click()
    URL.revokeObjectURL(url)
    setShowExportMenu(false)
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
    } catch (e) {
      console.error('Failed to copy:', e)
    }
  }

  const renderMessage = (m: any, i: number, isStreamingMsg = false) => {
    const content = isStreamingMsg ? streamingContent : m.content
    const isEditing = editingIndex === i
    return (
      <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
        <div
          className={`group/max-w-[85%] rounded-lg px-4 py-2 text-sm ${
            m.role === 'user'
              ? 'bg-cb-neon/20 border border-cb-neon/30 text-cb-text-bright shadow-neon-sm'
              : 'bg-cb-card border border-cb-border text-cb-text'
          }`}
        >
          {m.images && m.images.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {m.images.map((src: string, j: number) => (
                <img
                  key={j}
                  src={src}
                  alt={`Image ${j + 1}`}
                  className="max-h-32 rounded border border-cb-border"
                />
              ))}
            </div>
          )}

          {m.tool_calls && m.tool_calls.length > 0 && (
            <div className="mb-2 space-y-1">
              {m.tool_calls.map((tc: any, j: number) => (
                <ToolCallCard key={j} call={tc} />
              ))}
            </div>
          )}

          {isEditing ? (
            <div className="space-y-1">
              <textarea
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleEditConfirm() }
                  if (e.key === 'Escape') setEditingIndex(null)
                }}
                className="cb-input w-full resize-none"
                rows={3}
                autoFocus
              />
              <div className="flex gap-1 justify-end">
                <button onClick={handleEditConfirm} className="cb-btn-green text-xs px-2 py-0.5">
                  Save
                </button>
                <button onClick={() => setEditingIndex(null)} className="cb-btn-neon text-xs px-2 py-0.5">
                  Cancel
                </button>
              </div>
            </div>
          ) : m.role === 'assistant' ? (
            <div className="prose prose-invert prose-sm max-w-none prose-code:text-cb-gold prose-code:bg-cb-bg prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-pre:bg-cb-bg prose-pre:border prose-pre:border-cb-border">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {content}
              </ReactMarkdown>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{content}</p>
          )}

          {isStreamingMsg && streamingToolCalls.length > 0 && (
            <div className="mt-2 space-y-1">
              {streamingToolCalls.map((tc, j) => (
                <ToolCallCard key={j} call={tc} />
              ))}
            </div>
          )}

          {isStreamingMsg && (
            <span className="inline-block w-2 h-4 bg-cb-cyan animate-pulse ml-0.5 shadow-cyan-sm" />
          )}

          <div className="flex items-center gap-2 mt-1">
            {m.timestamp && !isStreamingMsg && (
              <p className="text-[10px] text-cb-muted opacity-60 font-mono">{new Date(m.timestamp).toLocaleTimeString()}</p>
            )}
            {!isStreamingMsg && m.role === 'assistant' && (
              <button
                onClick={() => handleCopy(m.content)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-cb-muted hover:text-cb-cyan"
                title="Copy message"
              >
                <Copy size={11} />
              </button>
            )}
            {!isStreamingMsg && m.role === 'user' && editingIndex !== i && (
              <button
                onClick={() => handleEditStart(i, m.content)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-cb-muted hover:text-cb-neon"
                title="Edit message"
              >
                <Pencil size={11} />
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 h-full overflow-hidden">
      <div className="flex flex-col flex-1 max-w-4xl mx-auto w-full relative">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-cb-border bg-cb-surface/80 backdrop-blur-sm shrink-0">
          <button
            onClick={() => setShowSessionSidebar(!showSessionSidebar)}
            className="text-xs text-cb-muted hover:text-cb-neon px-2 py-1 rounded border border-cb-border hover:border-cb-neon/50 transition-all hover:shadow-neon-sm"
          >
            {showSessionSidebar ? 'Hide' : 'Sessions'}
          </button>
          <div className="flex-1" />
          <ModelSelector sessionId={sessionId} className="mr-2" />
          <button
            onClick={() => setTtsEnabled(!ttsEnabled)}
            className={`p-1 rounded transition-colors ${ttsEnabled ? 'text-cb-neon cb-text-glow' : 'text-cb-muted hover:text-cb-cyan'}`}
            title={ttsEnabled ? 'TTS On' : 'TTS Off'}
          >
            {ttsEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="p-1 text-cb-muted hover:text-cb-cyan rounded transition-colors"
              title="Export chat"
            >
              <Download size={16} />
            </button>
            {showExportMenu && (
              <div className="absolute right-0 top-8 bg-cb-card border border-cb-border rounded-lg shadow-neon z-40 py-1 min-w-[120px]">
                <button
                  onClick={() => handleExport('md')}
                  className="w-full text-left px-3 py-1.5 text-xs text-cb-text hover:bg-cb-card-hover hover:text-cb-neon transition-colors"
                >
                  Export Markdown
                </button>
                <button
                  onClick={() => handleExport('json')}
                  className="w-full text-left px-3 py-1.5 text-xs text-cb-text hover:bg-cb-card-hover hover:text-cb-cyan transition-colors"
                >
                  Export JSON
                </button>
              </div>
            )}
          </div>
          <button
            onClick={() => setShowShortcuts(!showShortcuts)}
            className="p-1 text-cb-muted hover:text-cb-cyan rounded transition-colors"
            title="Keyboard shortcuts (Ctrl+?)"
          >
            <HelpCircle size={16} />
          </button>
          <button onClick={clear} className="text-cb-muted hover:text-cb-red rounded-lg px-2 py-1 transition-colors" title="Clear chat">
            <Trash2 size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !isStreaming && (
            <div className="text-center text-cb-muted mt-16">
              <Brain size={48} className="mx-auto mb-3 text-cb-neon/40 drop-shadow-[0_0_15px_rgba(140,82,255,0.3)]" />
              <p className="text-lg font-medium mb-2 text-cb-text-bright cb-text-glow">Ayassek Brain</p>
              <p className="text-sm mb-4">Send a message, paste an image, or type @ to reference entities</p>
              <div className="flex flex-wrap justify-center gap-2 text-xs text-cb-muted/60">
                {KEYBOARD_SHORTCUTS.map((s) => (
                  <kbd key={s.key} className="px-2 py-1 bg-cb-card border border-cb-border rounded text-cb-muted">
                    {s.key} — {s.action}
                  </kbd>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => renderMessage(m, i, m.isStreaming))}
          {isStreaming && messages[messages.length - 1]?.isStreaming && (
            <div className="flex justify-start">
              <div className="bg-cb-card border border-cb-border rounded-lg px-4 py-2 text-sm text-cb-muted animate-pulse">
                <span className="inline-block w-2 h-4 bg-cb-cyan animate-pulse mr-1 shadow-cyan-sm" />
                Thinking...
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {showMentions && filteredMentions.length > 0 && (
          <div className="absolute bottom-24 left-4 right-4 max-w-md bg-cb-card border border-cb-neon/20 rounded-xl shadow-neon z-30 max-h-48 overflow-y-auto">
            <div className="p-1.5 text-[10px] text-cb-muted uppercase tracking-wider border-b border-cb-border px-3 py-1">
              Entities
            </div>
            {filteredMentions.map((e, i) => (
              <button
                key={`${e.category}/${e.name}`}
                onClick={() => insertMention(e.name)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                  i === mentionIndex ? 'bg-cb-neon/10 text-cb-neon' : 'hover:bg-cb-card-hover'
                }`}
              >
                <AtSign size={14} className="text-cb-cyan shrink-0" />
                <span className="font-medium">{e.name}</span>
                <span className="text-xs text-cb-muted capitalize">{e.category}</span>
              </button>
            ))}
          </div>
        )}

        {isRecording && (
          <div className="border-t border-cb-red/30 bg-cb-red/10 px-4 py-2 flex items-center gap-3 backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-cb-red animate-glow-pulse shadow-red" />
            <span className="text-xs text-cb-red font-medium uppercase tracking-wider">Recording</span>
            <div className="flex-1 h-1 bg-cb-border rounded-full overflow-hidden">
              <div
                className="h-full bg-cb-red rounded-full transition-all shadow-red"
                style={{ width: `${Math.min(100, duration * 3.33)}%` }}
              />
            </div>
            <span className="text-xs text-cb-muted font-mono">{duration}s</span>
            <button
              onClick={() => {
                stopRecording()
                transcribeAudio((text) => {
                  if (text) {
                    setTranscribedText(text)
                    setInput(text)
                  }
                })
              }}
              className="cb-btn-red flex items-center gap-1 text-xs"
            >
              <Square size={10} /> Stop & Transcribe
            </button>
          </div>
        )}

        {/* Transcribed text bubble */}
        {transcribedText && (
          <div className="border-t border-cb-neon/30 bg-cb-neon/10 px-4 py-2 flex items-start gap-2 backdrop-blur-sm">
            <Mic size={14} className="text-cb-neon mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] text-cb-neon font-mono uppercase tracking-wider mb-0.5">Transcribed</p>
              <p className="text-xs text-cb-text leading-relaxed">{transcribedText}</p>
            </div>
            <button onClick={() => setTranscribedText('')} className="text-cb-muted hover:text-cb-cyan shrink-0 transition-colors">
              <X size={14} />
            </button>
          </div>
        )}

        {transcribing && (
          <div className="border-t border-cb-cyan/30 bg-cb-cyan/10 px-4 py-2 flex items-center gap-3 backdrop-blur-sm animate-glow-pulse">
            <span className="w-2 h-2 rounded-full bg-cb-cyan animate-pulse shadow-cyan" />
            <span className="text-xs text-cb-cyan font-medium uppercase tracking-wider">Transcribing...</span>
            <Loader2 size={14} className="animate-spin text-cb-cyan" />
          </div>
        )}

        {images.length > 0 && (
          <div className="border-t border-cb-border bg-cb-surface px-4 py-2">
            <div className="flex flex-wrap gap-2 items-center">
              {images.map((src, i) => (
                <ImagePreview key={i} src={src} onRemove={() => setImages((prev) => prev.filter((_, j) => j !== i))} />
              ))}
              <span className="text-[10px] text-cb-muted font-mono uppercase tracking-wider">{images.length} image(s) attached</span>
            </div>
          </div>
        )}

        {showContext && entities.length > 0 && (
          <div className="border-t border-cb-border bg-cb-surface/80 backdrop-blur-sm px-4 py-2">
            <button
              onClick={() => setShowContext(!showContext)}
              className="flex items-center gap-1 text-[10px] text-cb-muted hover:text-cb-neon mb-1 transition-colors uppercase tracking-wider"
            >
              <Brain size={12} className="text-cb-neon" />
              Relevant Context ({entities.length})
            </button>
            <div className="flex flex-wrap gap-1.5">
              {entities.slice(0, 5).map((e) => (
                <span
                  key={`${e.category}/${e.name}`}
                  className="flex items-center gap-1 text-[10px] bg-cb-bg border border-cb-border px-2 py-0.5 rounded"
                >
                  <span className="text-cb-cyan">&#x25C8;</span>
                  <span>{e.name}</span>
                  <span className="text-cb-muted/60 capitalize">({e.category})</span>
                </span>
              ))}
              {entities.length > 5 && (
                <span className="text-[10px] text-cb-muted">+{entities.length - 5} more</span>
              )}
            </div>
          </div>
        )}

        <div className="border-t border-cb-border p-4 bg-cb-surface/50 backdrop-blur-sm">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => handleInputChange(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder="Type a message... (@ to mention, paste images)"
                className="cb-input w-full pr-10"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button
                  onClick={isRecording ? stopRecording : startRecording}
                  className={`p-0.5 rounded transition-all ${
                    isRecording
                      ? 'text-cb-red animate-glow-pulse'
                      : 'text-cb-muted hover:text-cb-cyan'
                  }`}
                  title={isRecording ? 'Stop recording' : 'Record audio'}
                >
                  {isRecording ? <Square size={16} /> : <Mic size={16} />}
                </button>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="p-0.5 text-cb-muted hover:text-cb-cyan transition-colors"
                  title="Attach image"
                >
                  <Image size={16} />
                </button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={handleImageSelect}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={(!input.trim() && images.length === 0) || isStreaming}
              className="cb-btn-neon rounded-lg px-3 py-2 disabled:opacity-30"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>

      {showShortcuts && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-cb-bg/90 backdrop-blur-sm">
          <div className="bg-cb-card border border-cb-neon/30 rounded-xl shadow-neon-lg w-full max-w-md mx-4 p-4 animate-slide-in">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-cb-text-bright cb-text-glow flex items-center gap-2">
                <HelpCircle size={16} className="text-cb-neon" />
                Keyboard Shortcuts
              </h3>
              <button onClick={() => setShowShortcuts(false)} className="text-cb-muted hover:text-cb-cyan transition-colors">
                <X size={16} />
              </button>
            </div>
            <div className="space-y-2 max-h-[40vh] overflow-y-auto">
              {KEYBOARD_SHORTCUTS.map((s, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 px-2 bg-cb-surface/50 rounded-lg border border-cb-border/50">
                  <kbd className="px-2 py-0.5 text-[10px] font-mono bg-cb-bg border border-cb-border rounded text-cb-cyan">{s.key}</kbd>
                  <span className="text-xs text-cb-text ml-3 flex-1 text-left">{s.action}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-cb-muted mt-3 text-center">Press <kbd className="px-1 py-0.5 font-mono bg-cb-bg border border-cb-border rounded">Ctrl+?</kbd> again to close</p>
          </div>
        </div>
      )}

      {showSessionSidebar && <SessionSidebar />}
    </div>
  )
}
