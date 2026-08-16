/**
 * API contract tests.
 *
 * These assert the REQUEST the frontend sends, not just the response it
 * handles. The existing suite only ever mocked responses, so a field-name
 * mismatch between frontend and backend passed 590 tests while chat memory
 * was silently broken in the running app.
 *
 * Backend contract (backend/app/api/routes/chat.py):
 *   request  -> { message: str, session_id: str | null }
 *   response <- { response, session_id, intent, agent_calls, data_sources }
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'

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

const { useChat } = await import('../hooks/useChat')

let fetchMock: ReturnType<typeof vi.fn>

/** Parse the JSON body the frontend actually sent on the Nth fetch call. */
function sentBody(call = 0): Record<string, unknown> {
  const [, init] = fetchMock.mock.calls[call]
  return JSON.parse(init.body as string)
}

function okResponse(body: Record<string, unknown>) {
  return { ok: true, json: async () => body }
}

const CHAT_OK = {
  response: 'Friday looks clear.',
  session_id: 'sess-abc-123',
  intent: 'calendar_query',
  agent_calls: [],
  data_sources: [],
}

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('POST /api/chat request contract', () => {
  it('test_chat_request_uses_session_id_field', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    const body = sentBody()
    expect(body).toHaveProperty('session_id')
    // The backend has no conversation_id field — sending it starts a new
    // session on every turn, which is the bug this test exists to catch.
    expect(body).not.toHaveProperty('conversation_id')
  })

  it('test_chat_request_sends_message_text', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('What is happening Friday?')
    })

    expect(sentBody().message).toBe('What is happening Friday?')
  })

  it('test_first_message_sends_null_session_id', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('First')
    })

    expect(sentBody().session_id).toBeNull()
  })
})

describe('session continuity across turns', () => {
  it('test_session_id_from_response_is_reused_on_next_request', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('First')
    })
    await act(async () => {
      await result.current.sendMessage('Second')
    })

    // Turn two must carry the session the server handed back on turn one.
    expect(sentBody(1).session_id).toBe('sess-abc-123')
  })

  it('test_conversation_id_is_exposed_from_response_session_id', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(result.current.conversationId).toBe('sess-abc-123')
  })

  it('test_session_survives_three_turns', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    for (const text of ['one', 'two', 'three']) {
      await act(async () => {
        await result.current.sendMessage(text)
      })
    }

    expect(sentBody(1).session_id).toBe('sess-abc-123')
    expect(sentBody(2).session_id).toBe('sess-abc-123')
  })

  it('test_auth_token_sent_as_bearer_header', async () => {
    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('Hello', 'jwt-token-abc')
    })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer jwt-token-abc')
  })
})

describe('error surfacing', () => {
  it('test_429_sets_error_state', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 429,
      statusText: 'Too Many Requests',
      json: async () => ({ detail: 'JARVIS is thinking too fast' }),
    })

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(result.current.error).toBeTruthy()
    expect(result.current.error).toContain('429')
  })

  it('test_failed_request_clears_loading_state', async () => {
    fetchMock.mockRejectedValue(new Error('network down'))

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBe('network down')
  })

  it('test_error_cleared_on_next_successful_send', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'))
    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('Hello')
    })
    expect(result.current.error).toBe('network down')

    fetchMock.mockResolvedValue(okResponse(CHAT_OK))
    await act(async () => {
      await result.current.sendMessage('Again')
    })

    expect(result.current.error).toBeNull()
  })

  it('test_user_message_still_shown_when_request_fails', async () => {
    fetchMock.mockRejectedValue(new Error('network down'))

    const { result } = renderHook(() => useChat())
    await act(async () => {
      await result.current.sendMessage('Did this send?')
    })

    expect(result.current.messages.some(m => m.content === 'Did this send?')).toBe(true)
  })
})
