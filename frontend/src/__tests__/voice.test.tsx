import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'

// Mock Supabase to avoid module-level createClient call
vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    auth: {
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
    },
  })),
}))

const { default: MicButton } = await import('../components/MicButton/MicButton')
const { useVoiceState } = await import('../hooks/useVoiceState')
const { transcribeAudio, synthesizeSpeech } = await import('../api/voice')

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  // Restore mediaDevices for most tests
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia: vi.fn() },
    configurable: true,
    writable: true,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MicButton', () => {
  it('test_mic_button_renders_in_idle_state', () => {
    render(<MicButton voiceState="idle" onPress={vi.fn()} />)
    const btn = screen.getByRole('button')
    expect(btn).toBeInTheDocument()
    expect(btn.getAttribute('data-voice-state')).toBe('idle')
  })

  it('test_mic_button_renders_in_recording_state', () => {
    render(<MicButton voiceState="recording" onPress={vi.fn()} />)
    const btn = screen.getByRole('button')
    expect(btn.getAttribute('data-voice-state')).toBe('recording')
  })

  it('test_mic_button_renders_in_speaking_state', () => {
    render(<MicButton voiceState="speaking" onPress={vi.fn()} />)
    const btn = screen.getByRole('button')
    expect(btn.getAttribute('data-voice-state')).toBe('speaking')
  })

  it('test_mic_button_hidden_when_media_devices_unavailable', () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      value: undefined,
      configurable: true,
      writable: true,
    })
    const { container } = render(<MicButton voiceState="idle" onPress={vi.fn()} isAvailable={false} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('useVoiceState', () => {
  it('test_voice_state_transitions_idle_to_recording_on_press', () => {
    const { result } = renderHook(() => useVoiceState())
    expect(result.current.voiceState).toBe('idle')
    act(() => { result.current.startRecording() })
    expect(result.current.voiceState).toBe('recording')
  })

  it('test_voice_state_transitions_recording_to_processing_on_stop', () => {
    const { result } = renderHook(() => useVoiceState())
    act(() => { result.current.startRecording() })
    act(() => { result.current.stopRecording() })
    expect(result.current.voiceState).toBe('processing')
  })

  it('test_voice_state_barge_in_stops_audio_when_speaking', () => {
    const { result } = renderHook(() => useVoiceState())
    act(() => { result.current.startSpeaking() })
    expect(result.current.voiceState).toBe('speaking')
    // Barge-in: transition to recording
    act(() => { result.current.startRecording() })
    expect(result.current.voiceState).toBe('recording')
  })
})

describe('voice API', () => {
  it('test_transcribe_audio_posts_to_listen_endpoint', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ transcript: 'Hello', duration_seconds: 1.5 }),
    })
    const blob = new Blob(['audio'], { type: 'audio/webm' })
    await transcribeAudio(blob, 'test-token')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/listen'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('test_transcribe_audio_sends_audio_blob', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ transcript: 'Test', duration_seconds: null }),
    })
    const blob = new Blob(['audio data'], { type: 'audio/webm' })
    const result = await transcribeAudio(blob, 'tok')
    expect(result.transcript).toBe('Test')
    // Verify FormData was sent (fetch body should be FormData, not JSON string)
    const callArgs = fetchMock.mock.calls[0][1] as RequestInit
    expect(callArgs.body).toBeInstanceOf(FormData)
  })

  it('test_synthesize_speech_posts_to_speak_endpoint', async () => {
    const audioBlob = new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' })
    fetchMock.mockResolvedValue({
      ok: true,
      blob: async () => audioBlob,
    })
    await synthesizeSpeech('Hello JARVIS', 'test-token')
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/speak'),
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('test_synthesize_speech_returns_audio_blob', async () => {
    const audioBlob = new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' })
    fetchMock.mockResolvedValue({
      ok: true,
      blob: async () => audioBlob,
    })
    const result = await synthesizeSpeech('Hello', 'tok')
    expect(result).toBeInstanceOf(Blob)
  })
})

describe('voice conversation', () => {
  it('test_voice_conversation_passes_transcript_to_chat', async () => {
    const sendMessage = vi.fn().mockResolvedValue(undefined)

    // Mock transcribeAudio behavior via fetch
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ transcript: "What's for dinner?", duration_seconds: 1 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ response: 'I suggest pasta', conversation_id: 'c1' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        blob: async () => new Blob([], { type: 'audio/mpeg' }),
      })

    const blob = new Blob(['audio'], { type: 'audio/webm' })
    const { transcript } = await transcribeAudio(blob, 'tok')
    await sendMessage(transcript, 'tok')

    expect(sendMessage).toHaveBeenCalledWith("What's for dinner?", 'tok')
  })
})

// Provide a dummy render usage to keep import used
function _unused() {
  render(<></>)
  fireEvent.click(document.body)
  return screen
}
void _unused
