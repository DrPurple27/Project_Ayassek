import { useState, useEffect } from 'react'
import { Settings, Volume2, Mic, Cpu, Server, Database, Save, RefreshCw, Check, X, ChevronDown, Loader2 } from 'lucide-react'
import { api } from '@/api/client'

// ─── Voice Settings ───────────────────────────────────────────────

interface VoiceSettings {
  stt: { enabled: boolean; model: string; device: string; compute_type: string; language: string }
  tts: { enabled: boolean; engine: string; lang_code: string; voice: string; sample_rate: number }
  stt_available: boolean
  tts_available: boolean
}

const STT_MODELS = ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3', 'distil-large-v3']
const STT_DEVICES = ['auto', 'cpu', 'cuda']
const COMPUTE_TYPES = ['int8', 'float16', 'float32']
const LANGUAGES = [
  { value: 'pt', label: 'Portuguese' }, { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' }, { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' }, { value: 'it', label: 'Italian' },
  { value: 'ja', label: 'Japanese' }, { value: 'zh', label: 'Chinese' },
  { value: 'auto', label: 'Auto-detect' },
]
const TTS_VOICES = ['af_heart', 'af_bella', 'af_nicole', 'af_sarah', 'am_adam', 'am_michael', 'bf_emma', 'bf_isabella', 'bm_george', 'bm_lewis']

function VoiceSettingsSection() {
  const [settings, setSettings] = useState<VoiceSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.getVoiceSettings().then(setSettings).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    if (!settings) return
    setSaving(true)
    try {
      await api.updateVoiceSettings({ stt: settings.stt, tts: settings.tts })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e: unknown) {
      console.warn('Failed to save', e instanceof Error ? e.message : e)
    }
    setSaving(false)
  }

  const updateSTT = (key: string, value: any) => {
    if (!settings) return
    setSettings({ ...settings, stt: { ...settings.stt, [key]: value } })
  }

  const updateTTS = (key: string, value: any) => {
    if (!settings) return
    setSettings({ ...settings, tts: { ...settings.tts, [key]: value } })
  }

  if (loading) return <div className="flex items-center gap-2 text-cb-muted text-sm py-8"><RefreshCw size={16} className="animate-spin text-cb-neon" /> Loading voice settings...</div>
  if (!settings) return <div className="text-cb-red py-8">Failed to load voice settings</div>

  return (
    <div className="space-y-6">
      {/* STT */}
      <div className="cb-panel rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-cb-text-bright flex items-center gap-2">
            <Mic size={16} className="text-cb-cyan" />
            Speech-to-Text
            <span className="text-[10px] font-mono text-cb-muted">(faster-whisper)</span>
          </h3>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.stt.enabled}
                onChange={(e) => updateSTT('enabled', e.target.checked)}
                className="w-3.5 h-3.5 rounded border-cb-border bg-cb-bg text-cb-neon focus:ring-cb-neon"
              />
              <span className="text-[10px] text-cb-muted font-mono">Enable</span>
            </label>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${
              settings.stt_available ? 'bg-cb-green/15 text-cb-green border-cb-green/30' : 'bg-cb-red/15 text-cb-red border-cb-red/30'
            }`}>
              {settings.stt_available ? 'Available' : 'Unavailable'}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Model Size</span>
            <select value={settings.stt.model} onChange={(e) => updateSTT('model', e.target.value)} className="cb-input w-full">
              {STT_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Language</span>
            <select value={settings.stt.language} onChange={(e) => updateSTT('language', e.target.value)} className="cb-input w-full">
              {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Device</span>
            <select value={settings.stt.device} onChange={(e) => updateSTT('device', e.target.value)} className="cb-input w-full">
              {STT_DEVICES.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Compute Type</span>
            <select value={settings.stt.compute_type} onChange={(e) => updateSTT('compute_type', e.target.value)} className="cb-input w-full">
              {COMPUTE_TYPES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        </div>
      </div>

      {/* TTS */}
      <div className="cb-panel rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-cb-text-bright flex items-center gap-2">
            <Volume2 size={16} className="text-cb-pink" />
            Text-to-Speech
            <span className="text-[10px] font-mono text-cb-muted">(Kokoro-82M)</span>
          </h3>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.tts.enabled}
                onChange={(e) => updateTTS('enabled', e.target.checked)}
                className="w-3.5 h-3.5 rounded border-cb-border bg-cb-bg text-cb-pink focus:ring-cb-pink"
              />
              <span className="text-[10px] text-cb-muted font-mono">Enable</span>
            </label>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${
              settings.tts_available ? 'bg-cb-green/15 text-cb-green border-cb-green/30' : 'bg-cb-red/15 text-cb-red border-cb-red/30'
            }`}>
              {settings.tts_available ? 'Available' : 'Unavailable'}
            </span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Voice</span>
            <select value={settings.tts.voice} onChange={(e) => updateTTS('voice', e.target.value)} className="cb-input w-full">
              {TTS_VOICES.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Language Code</span>
            <select value={settings.tts.lang_code} onChange={(e) => updateTTS('lang_code', e.target.value)} className="cb-input w-full">
              <option value="a">American English</option>
              <option value="b">British English</option>
              <option value="j">Japanese</option>
              <option value="z">Chinese</option>
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-xs text-cb-muted uppercase tracking-wider font-mono">Sample Rate</span>
            <select value={settings.tts.sample_rate} onChange={(e) => updateTTS('sample_rate', parseInt(e.target.value))} className="cb-input w-full">
              <option value={16000}>16000 Hz</option>
              <option value={22050}>22050 Hz</option>
              <option value={24000}>24000 Hz</option>
              <option value={44100}>44100 Hz</option>
            </select>
          </label>
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving} className={`cb-btn-green flex items-center gap-2 disabled:opacity-30 ${saved ? 'shadow-green' : ''}`}>
          <Save size={14} />
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Voice Settings'}
        </button>
      </div>
    </div>
  )
}

// ─── Provider Cards ───────────────────────────────────────────────

function ProviderSettingsSection() {
  const [providers, setProviders] = useState<any[]>([])
  const [activeProvider, setActiveProvider] = useState('')
  const [activeModel, setActiveModel] = useState('')
  const [loading, setLoading] = useState(true)
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null)
  const [modelsMap, setModelsMap] = useState<Record<string, any[]>>({})
  const [modelsLoading, setModelsLoading] = useState<string | null>(null)

  useEffect(() => {
    api.getProviders().then((res) => {
      setProviders(res.providers)
      setActiveProvider(res.active_provider)
      setActiveModel(res.active_model)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const handleProviderClick = async (providerId: string) => {
    if (expandedProvider === providerId) {
      setExpandedProvider(null)
      return
    }
    setExpandedProvider(providerId)
    if (!modelsMap[providerId]) {
      setModelsLoading(providerId)
      try {
        const res = await api.getModels(providerId)
        setModelsMap((prev) => ({ ...prev, [providerId]: res.models || [] }))
      } catch (e: unknown) {
        console.error('Failed to load models:', e instanceof Error ? e.message : e)
      }
      setModelsLoading(null)
    }
  }

  const handleSelectModel = async (providerId: string, modelId: string) => {
    try {
      await api.setActiveProvider(providerId, modelId)
      setActiveProvider(providerId)
      setActiveModel(modelId)
      setExpandedProvider(null)
    } catch (e: unknown) {
      console.error('Failed to set provider:', e instanceof Error ? e.message : e)
    }
  }

  if (loading) return <div className="flex items-center gap-2 text-cb-muted text-sm py-8"><RefreshCw size={16} className="animate-spin text-cb-neon" /> Loading providers...</div>

  return (
    <div className="space-y-3">
      <p className="text-xs text-cb-muted font-mono uppercase tracking-wider">
        Active: <span className="text-cb-neon">{activeProvider}</span> / <span className="text-cb-cyan">{activeModel}</span>
      </p>
      {providers.map((p) => {
        const isExpanded = expandedProvider === p.id
        const isActive = activeProvider === p.id
        return (
          <div key={p.id} className={`cb-panel rounded-xl overflow-hidden border ${isActive ? 'border-cb-neon/30' : 'border-cb-border'}`}>
            <button
              onClick={() => handleProviderClick(p.id)}
              className="w-full flex items-center gap-3 p-4 hover:bg-cb-card-hover transition-colors text-left"
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isActive ? 'bg-cb-neon/20 text-cb-neon' : 'bg-cb-surface text-cb-muted'} border border-cb-border`}>
                <Cpu size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-medium text-cb-text-bright truncate">{p.name || p.id}</h4>
                {isActive && <p className="text-[10px] text-cb-cyan font-mono mt-0.5">Active · Model: {activeModel}</p>}
              </div>
              <div className="flex items-center gap-2">
                {isActive && <Check size={14} className="text-cb-green" />}
                {modelsLoading === p.id ? (
                  <Loader2 size={14} className="animate-spin text-cb-cyan" />
                ) : (
                  <ChevronDown size={14} className={`text-cb-muted transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                )}
              </div>
            </button>
            {isExpanded && (
              <div className="border-t border-cb-border p-3 space-y-1 max-h-48 overflow-y-auto">
                {modelsMap[p.id]?.map((m: any) => (
                  <button
                    key={m.id}
                    onClick={() => handleSelectModel(p.id, m.id)}
                    className={`w-full text-left px-3 py-2 text-xs rounded-lg transition-colors ${
                      activeProvider === p.id && activeModel === m.id
                        ? 'bg-cb-neon/10 text-cb-neon border border-cb-neon/30'
                        : 'text-cb-text hover:bg-cb-card-hover border border-transparent'
                    }`}
                  >
                    <span className="font-medium">{m.id}</span>
                    {m.description && <p className="text-cb-muted text-[10px] mt-0.5 truncate">{m.description}</p>}
                  </button>
                ))}
                {(!modelsMap[p.id] || modelsMap[p.id].length === 0) && (
                  <p className="text-xs text-cb-muted italic py-2 text-center">No models available</p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── System Info ──────────────────────────────────────────────────

function SystemInfoSection() {
  const [sysInfo, setSysInfo] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getReady().then((res) => setSysInfo(res)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="flex items-center gap-2 text-cb-muted text-sm py-8"><RefreshCw size={16} className="animate-spin text-cb-neon" /> Loading system info...</div>

  const items = sysInfo ? [
    { icon: Server, label: 'Status', value: sysInfo.ready ? 'Ready' : 'Not Ready', color: sysInfo.ready ? 'text-cb-green' : 'text-cb-gold' },
    { icon: Database, label: 'Steps', value: `${sysInfo.steps?.length || 0} configured`, color: 'text-cb-cyan' },
  ] : [
    { icon: Server, label: 'Status', value: 'Unknown', color: 'text-cb-muted' },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {items.map((item, i) => (
          <div key={i} className="cb-panel rounded-xl p-4 flex items-center gap-3">
            <item.icon size={20} className={item.color} />
            <div>
              <p className="text-[10px] text-cb-muted uppercase tracking-wider font-mono">{item.label}</p>
              <p className="text-sm font-medium text-cb-text-bright">{item.value}</p>
            </div>
          </div>
        ))}
      </div>

      {sysInfo?.steps && sysInfo.steps.length > 0 && (
        <div className="cb-panel rounded-xl p-4 space-y-2">
          <h4 className="text-xs text-cb-muted uppercase tracking-wider font-mono">Startup Steps</h4>
          {sysInfo.steps.map((step: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className={`w-4 h-4 rounded-full flex items-center justify-center ${
                step.status === 'ok' ? 'bg-cb-green/20 text-cb-green' :
                step.status === 'skipped' ? 'bg-cb-gold/20 text-cb-gold' :
                step.status === 'error' ? 'bg-cb-red/20 text-cb-red' :
                'bg-cb-muted/20 text-cb-muted'
              }`}>
                {step.status === 'ok' ? <Check size={10} /> : step.status === 'error' ? <X size={10} /> : '–'}
              </span>
              <span className="text-cb-text flex-1">{step.name || step.step}</span>
              {step.error && <span className="text-cb-red text-[10px]">{step.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main Settings Panel ──────────────────────────────────────────

type SettingsTab = 'voice' | 'providers' | 'system'

const TABS: { id: SettingsTab; icon: any; label: string }[] = [
  { id: 'voice', icon: Volume2, label: 'Voice' },
  { id: 'providers', icon: Cpu, label: 'Providers' },
  { id: 'system', icon: Server, label: 'System' },
]

export default function SettingsPanel() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('voice')

  return (
    <div className="max-w-3xl mx-auto w-full p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Settings size={24} className="text-cb-neon" />
        <h2 className="text-lg font-semibold text-cb-text-bright cb-text-glow">Settings</h2>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-cb-surface rounded-xl p-1 border border-cb-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-lg transition-all ${
              activeTab === tab.id
                ? 'bg-cb-neon/15 text-cb-neon cb-text-glow shadow-neon-sm'
                : 'text-cb-muted hover:text-cb-text hover:bg-cb-card-hover'
            }`}
          >
            <tab.icon size={16} />
            <span className="font-medium">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="min-h-[300px]">
        {activeTab === 'voice' && <VoiceSettingsSection />}
        {activeTab === 'providers' && <ProviderSettingsSection />}
        {activeTab === 'system' && <SystemInfoSection />}
      </div>
    </div>
  )
}
