import type { VoiceState } from '../../hooks/useVoiceState'
import styles from './MicButton.module.css'

interface MicButtonProps {
  voiceState: VoiceState
  onPress: () => void
  isAvailable?: boolean
}

export default function MicButton({
  voiceState,
  onPress,
  isAvailable = true,
}: MicButtonProps) {
  if (!isAvailable) {
    return null
  }

  const stateClass = styles[voiceState] ?? ''

  const labels: Record<VoiceState, string> = {
    idle: 'Start voice input',
    recording: 'Stop recording',
    processing: 'Processing...',
    speaking: 'JARVIS is speaking — tap to interrupt',
  }

  return (
    <button
      className={`${styles.micBtn} ${stateClass}`}
      onClick={onPress}
      aria-label={labels[voiceState]}
      type="button"
      data-voice-state={voiceState}
    >
      <MicIcon voiceState={voiceState} />
    </button>
  )
}

function MicIcon({ voiceState }: { voiceState: VoiceState }) {
  if (voiceState === 'speaking') {
    return (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
      </svg>
    )
  }

  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z" />
    </svg>
  )
}
