import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { renderHook } from '@testing-library/react'

// Mock Supabase
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

const { default: MessageThread } = await import('../components/MessageThread/MessageThread')
const { default: MessageBubble } = await import('../components/MessageBubble/MessageBubble')
const { default: ChatInput } = await import('../components/ChatInput/ChatInput')
const { default: ThinkingIndicator } = await import('../components/ThinkingIndicator/ThinkingIndicator')
const { useChat } = await import('../hooks/useChat')

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MessageThread', () => {
  it('test_message_thread_renders_messages', () => {
    const messages = [
      { id: '1', role: 'user' as const, content: 'Hello JARVIS' },
      { id: '2', role: 'assistant' as const, content: 'Hello, how can I help?' },
    ]
    render(<MessageThread messages={messages} />)
    expect(screen.getByText('Hello JARVIS')).toBeInTheDocument()
    expect(screen.getByText('Hello, how can I help?')).toBeInTheDocument()
  })

  it('test_message_thread_renders_empty_state', () => {
    render(<MessageThread messages={[]} />)
    expect(screen.getByTestId('message-thread')).toBeInTheDocument()
    expect(screen.getByText(/JARVIS is ready/i)).toBeInTheDocument()
  })
})

describe('MessageBubble', () => {
  it('test_message_bubble_user_variant_renders', () => {
    const msg = { id: '1', role: 'user' as const, content: 'Test' }
    render(<MessageBubble message={msg} />)
    const wrapper = screen.getByText('Test').closest('[data-role="user"]')
    expect(wrapper).toBeInTheDocument()
  })

  it('test_message_bubble_jarvis_variant_renders', () => {
    const msg = { id: '1', role: 'assistant' as const, content: 'Test reply' }
    render(<MessageBubble message={msg} />)
    const wrapper = screen.getByText('Test reply').closest('[data-role="assistant"]')
    expect(wrapper).toBeInTheDocument()
  })

  it('test_message_bubble_displays_content', () => {
    const msg = { id: '1', role: 'user' as const, content: 'Specific content here' }
    render(<MessageBubble message={msg} />)
    expect(screen.getByText('Specific content here')).toBeInTheDocument()
  })
})

describe('ChatInput', () => {
  it('test_chat_input_calls_on_submit_on_enter', () => {
    const onSubmit = vi.fn()
    render(<ChatInput onSubmit={onSubmit} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Hello' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    expect(onSubmit).toHaveBeenCalledWith('Hello')
  })

  it('test_chat_input_disabled_while_loading', () => {
    render(<ChatInput onSubmit={vi.fn()} disabled={true} />)
    const textarea = screen.getByRole('textbox')
    expect(textarea).toBeDisabled()
  })

  it('test_chat_input_clears_after_submit', () => {
    render(<ChatInput onSubmit={vi.fn()} />)
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'Hello' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    expect(textarea).toHaveValue('')
  })
})

describe('ThinkingIndicator', () => {
  it('test_thinking_indicator_renders_when_loading', () => {
    render(<ThinkingIndicator />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})

describe('useChat hook', () => {
  it('test_use_chat_adds_user_message_to_thread', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'JARVIS response', session_id: 'conv1' }),
    })

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('Test message')
    })

    expect(result.current.messages.some(m => m.role === 'user' && m.content === 'Test message')).toBe(true)
  })

  it('test_use_chat_adds_jarvis_response_to_thread', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'Hello from JARVIS', session_id: 'conv1' }),
    })

    const { result } = renderHook(() => useChat())

    await act(async () => {
      await result.current.sendMessage('Hello')
    })

    expect(result.current.messages.some(m => m.role === 'assistant' && m.content === 'Hello from JARVIS')).toBe(true)
  })

  it('test_use_chat_sets_loading_state_during_request', async () => {
    let resolveResponse: (value: unknown) => void
    const pendingPromise = new Promise(resolve => { resolveResponse = resolve })

    fetchMock.mockReturnValue(pendingPromise)

    const { result } = renderHook(() => useChat())

    act(() => {
      void result.current.sendMessage('Test')
    })

    // Loading should be true while waiting
    expect(result.current.loading).toBe(true)

    // Resolve the fetch
    await act(async () => {
      resolveResponse!({
        ok: true,
        json: async () => ({ response: 'done', session_id: 'c1' }),
      })
      await pendingPromise
    })

    expect(result.current.loading).toBe(false)
  })
})

function renderInRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

// Make renderInRouter used (keeps TS happy)
void renderInRouter

// --- Chat page error banner --------------------------------------------------
//
// Request failures (notably free-tier 429s) used to fail silently: the
// thinking indicator stopped and nothing else happened.

const { default: ChatPage } = await import('../pages/Chat')
const { AuthProvider } = await import('../contexts/AuthContext')

describe('Chat page error surfacing', () => {
  function renderChatPage() {
    return render(
      <MemoryRouter>
        <AuthProvider>
          <ChatPage />
        </AuthProvider>
      </MemoryRouter>,
    )
  }

  it('test_chat_page_shows_error_banner_on_failed_send', async () => {
    fetchMock.mockRejectedValue(new Error('429 Too Many Requests'))

    await act(async () => { renderChatPage() })

    const textarea = screen.getByRole('textbox')
    await act(async () => {
      fireEvent.change(textarea, { target: { value: 'Hello' } })
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    })

    expect(await screen.findByText(/429 Too Many Requests/)).toBeInTheDocument()
  })

  it('test_chat_page_has_no_error_banner_initially', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ response: 'hi', session_id: 's1' }),
    })

    await act(async () => { renderChatPage() })

    expect(screen.queryByText(/Too Many Requests/)).not.toBeInTheDocument()
  })
})
