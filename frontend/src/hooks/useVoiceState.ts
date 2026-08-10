import { useState, useCallback } from 'react'

export type VoiceState = 'idle' | 'recording' | 'processing' | 'speaking'

interface UseVoiceStateReturn {
  voiceState: VoiceState
  startRecording: () => void
  stopRecording: () => void
  startProcessing: () => void
  startSpeaking: () => void
  stopSpeaking: () => void
}

export function useVoiceState(): UseVoiceStateReturn {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')

  const startRecording = useCallback(() => {
    setVoiceState('recording')
  }, [])

  const stopRecording = useCallback(() => {
    setVoiceState('processing')
  }, [])

  const startProcessing = useCallback(() => {
    setVoiceState('processing')
  }, [])

  const startSpeaking = useCallback(() => {
    setVoiceState('speaking')
  }, [])

  const stopSpeaking = useCallback(() => {
    setVoiceState('idle')
  }, [])

  return {
    voiceState,
    startRecording,
    stopRecording,
    startProcessing,
    startSpeaking,
    stopSpeaking,
  }
}
