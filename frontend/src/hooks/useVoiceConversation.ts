import { useRef, useCallback } from 'react'
import { useVoiceState } from './useVoiceState'
import { useAudioRecorder } from './useAudioRecorder'
import { transcribeAudio, synthesizeSpeech } from '../api/voice'

interface UseVoiceConversationOptions {
  /** Must resolve with JARVIS's reply — that is what gets spoken. */
  sendMessage: (text: string, token?: string) => Promise<string | null>
  token: string | undefined
  onTranscript?: (text: string) => void
}

interface UseVoiceConversationReturn {
  voiceState: ReturnType<typeof useVoiceState>['voiceState']
  isAvailable: boolean
  handleMicPress: () => void
}

export function useVoiceConversation({
  sendMessage,
  token,
  onTranscript,
}: UseVoiceConversationOptions): UseVoiceConversationReturn {
  const { voiceState, startRecording, stopRecording, startSpeaking, stopSpeaking } =
    useVoiceState()
  const { start: startRecorder, stop: stopRecorder } = useAudioRecorder()
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const isAvailable = typeof navigator !== 'undefined' && !!navigator.mediaDevices

  const handleMicPress = useCallback(async () => {
    if (voiceState === 'speaking') {
      // Barge-in: stop current audio and start recording
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      startRecording()
      await startRecorder()
      return
    }

    if (voiceState === 'recording') {
      stopRecording() // transitions to 'processing'
      try {
        const blob = await stopRecorder()
        if (!token) return

        const { transcript } = await transcribeAudio(blob, token)
        if (onTranscript) onTranscript(transcript)

        const reply = await sendMessage(transcript, token)

        // Speak JARVIS's reply — never the transcript. Synthesizing the
        // transcript makes JARVIS parrot the user back instead of answering.
        if (!reply) {
          stopSpeaking()
          return
        }

        startSpeaking()
        const audioBlob = await synthesizeSpeech(reply, token)
        const url = URL.createObjectURL(audioBlob)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => {
          URL.revokeObjectURL(url)
          audioRef.current = null
          stopSpeaking()
        }
        await audio.play()
      } catch {
        stopSpeaking()
      }
      return
    }

    if (voiceState === 'idle') {
      startRecording()
      await startRecorder()
    }
  }, [voiceState, token, startRecording, stopRecording, startSpeaking, stopSpeaking, startRecorder, stopRecorder, sendMessage, onTranscript])

  return {
    voiceState,
    isAvailable,
    handleMicPress,
  }
}
