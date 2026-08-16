/**
 * useVoiceConversation hook tests.
 *
 * The existing voice suite never invoked this hook — it hand-rolled the flow by
 * calling transcribeAudio and a stub sendMessage in sequence. So it could not
 * see that the hook synthesized the *transcript* rather than JARVIS's reply,
 * which made JARVIS read the user's own words back instead of answering.
 *
 * These tests drive the real hook and assert what gets spoken.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'

const transcribeAudio = vi.fn()
const synthesizeSpeech = vi.fn()
const startRecorder = vi.fn()
const stopRecorder = vi.fn()

vi.mock('../api/voice', () => ({
  transcribeAudio: (...args: unknown[]) => transcribeAudio(...args),
  synthesizeSpeech: (...args: unknown[]) => synthesizeSpeech(...args),
}))

vi.mock('../hooks/useAudioRecorder', () => ({
  useAudioRecorder: () => ({ start: startRecorder, stop: stopRecorder }),
}))

const { useVoiceConversation } = await import('../hooks/useVoiceConversation')

const TRANSCRIPT = "What's for dinner?"
const REPLY = 'I suggest pasta with the chicken you have.'

let playMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  vi.clearAllMocks()

  transcribeAudio.mockResolvedValue({ transcript: TRANSCRIPT, duration_seconds: 1 })
  synthesizeSpeech.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])], { type: 'audio/mpeg' }))
  startRecorder.mockResolvedValue(undefined)
  stopRecorder.mockResolvedValue(new Blob(['audio'], { type: 'audio/webm' }))

  playMock = vi.fn().mockResolvedValue(undefined)
  vi.stubGlobal('Audio', class {
    onended: (() => void) | null = null
    play = playMock
    pause = vi.fn()
  })
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:fake'),
    revokeObjectURL: vi.fn(),
  })
  vi.stubGlobal('navigator', { mediaDevices: {} })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Run a full press-to-record, press-to-send cycle. */
async function runVoiceTurn(sendMessage: ReturnType<typeof vi.fn>) {
  const { result } = renderHook(() =>
    useVoiceConversation({ sendMessage, token: 'tok' }),
  )

  await act(async () => { await result.current.handleMicPress() })  // start recording
  await act(async () => { await result.current.handleMicPress() })  // stop + send

  return result
}

describe('useVoiceConversation', () => {
  it('test_speaks_jarvis_reply_not_the_transcript', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    await runVoiceTurn(sendMessage)

    // The bug: synthesizeSpeech was called with the transcript, so JARVIS
    // repeated the user instead of answering.
    expect(synthesizeSpeech).toHaveBeenCalledWith(REPLY, 'tok')
    expect(synthesizeSpeech).not.toHaveBeenCalledWith(TRANSCRIPT, 'tok')
  })

  it('test_sends_transcript_to_chat', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    await runVoiceTurn(sendMessage)

    expect(sendMessage).toHaveBeenCalledWith(TRANSCRIPT, 'tok')
  })

  it('test_transcribes_recorded_audio', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    await runVoiceTurn(sendMessage)

    expect(transcribeAudio).toHaveBeenCalledTimes(1)
  })

  it('test_plays_synthesized_audio', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    await runVoiceTurn(sendMessage)

    expect(playMock).toHaveBeenCalled()
  })

  it('test_onTranscript_receives_user_words', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    const onTranscript = vi.fn()

    const { result } = renderHook(() =>
      useVoiceConversation({ sendMessage, token: 'tok', onTranscript }),
    )
    await act(async () => { await result.current.handleMicPress() })
    await act(async () => { await result.current.handleMicPress() })

    expect(onTranscript).toHaveBeenCalledWith(TRANSCRIPT)
  })
})

describe('failure handling', () => {
  it('test_does_not_speak_when_chat_fails', async () => {
    // sendMessage resolves null when the request failed — speaking the
    // transcript here would be the same parroting bug in a different guise.
    const sendMessage = vi.fn().mockResolvedValue(null)
    await runVoiceTurn(sendMessage)

    expect(synthesizeSpeech).not.toHaveBeenCalled()
  })

  it('test_returns_to_idle_when_chat_fails', async () => {
    const sendMessage = vi.fn().mockResolvedValue(null)
    const result = await runVoiceTurn(sendMessage)

    expect(result.current.voiceState).toBe('idle')
  })

  it('test_returns_to_idle_when_synthesis_fails', async () => {
    synthesizeSpeech.mockRejectedValue(new Error('502 Bad Gateway'))
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    const result = await runVoiceTurn(sendMessage)

    expect(result.current.voiceState).toBe('idle')
  })

  it('test_does_not_speak_when_empty_reply', async () => {
    const sendMessage = vi.fn().mockResolvedValue('')
    await runVoiceTurn(sendMessage)

    expect(synthesizeSpeech).not.toHaveBeenCalled()
  })
})

describe('recording state machine', () => {
  it('test_first_press_starts_recording', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    const { result } = renderHook(() =>
      useVoiceConversation({ sendMessage, token: 'tok' }),
    )

    await act(async () => { await result.current.handleMicPress() })

    expect(result.current.voiceState).toBe('recording')
    expect(startRecorder).toHaveBeenCalled()
  })

  it('test_unavailable_without_media_devices', () => {
    vi.stubGlobal('navigator', {})
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    const { result } = renderHook(() =>
      useVoiceConversation({ sendMessage, token: 'tok' }),
    )

    expect(result.current.isAvailable).toBe(false)
  })

  it('test_no_send_without_token', async () => {
    const sendMessage = vi.fn().mockResolvedValue(REPLY)
    const { result } = renderHook(() =>
      useVoiceConversation({ sendMessage, token: undefined }),
    )

    await act(async () => { await result.current.handleMicPress() })
    await act(async () => { await result.current.handleMicPress() })

    expect(sendMessage).not.toHaveBeenCalled()
    expect(synthesizeSpeech).not.toHaveBeenCalled()
  })
})
