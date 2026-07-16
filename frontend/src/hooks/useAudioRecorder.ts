import { useState, useRef, useCallback } from 'react'
import { api } from '@/api/client'

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [duration, setDuration] = useState(0)
  const [transcribing, setTranscribing] = useState(false)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startTimeRef = useRef(0)

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const url = URL.createObjectURL(blob)
        setAudioUrl(url)
        stream.getTracks().forEach((t) => t.stop())
        if (timerRef.current) clearInterval(timerRef.current)
      }

      mediaRecorder.start()
      startTimeRef.current = Date.now()
      setIsRecording(true)
      setDuration(0)

      timerRef.current = setInterval(() => {
        setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 200)
    } catch (e: unknown) {
      console.error('Failed to start recording:', e instanceof Error ? e.message : e)
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    setIsRecording(false)
  }, [])

  const getAudioBlob = useCallback((): Blob | null => {
    if (chunksRef.current.length === 0) return null
    return new Blob(chunksRef.current, { type: 'audio/webm' })
  }, [])

  const transcribeAudio = useCallback(async (onResult?: (text: string) => void): Promise<string | null> => {
    const blob = getAudioBlob()
    if (!blob) return null

    setTranscribing(true)
    try {
      const formData = new FormData()
      formData.append('audio', blob, 'recording.webm')
      formData.append('language', 'pt-BR')

      const res = await api.transcribeVoice(formData)
      if (onResult && res.text) {
        onResult(res.text)
      }
      return res.text || null
    } catch (e: unknown) {
      console.error('Transcription failed:', e instanceof Error ? e.message : e)
      return null
    } finally {
      setTranscribing(false)
    }
  }, [getAudioBlob])

  const clearAudio = useCallback(() => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
    setDuration(0)
    chunksRef.current = []
  }, [audioUrl])

  return {
    isRecording,
    audioUrl,
    duration,
    transcribing,
    startRecording,
    stopRecording,
    getAudioBlob,
    transcribeAudio,
    clearAudio,
  }
}