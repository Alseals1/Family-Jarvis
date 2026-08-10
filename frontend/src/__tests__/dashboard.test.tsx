import { render, screen, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { renderHook } from '@testing-library/react'

// Mutable auth mock
const authMock = {
  signInWithPassword: vi.fn(),
  signOut: vi.fn().mockResolvedValue({}),
  getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token', user: { id: 'u1' } } } }),
  onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
}

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({ auth: authMock })),
}))

const { default: MainLayout } = await import('../components/MainLayout/MainLayout')
const { default: BriefingCard } = await import('../components/BriefingCard/BriefingCard')
const { default: NotificationsPanel } = await import('../components/NotificationsPanel/NotificationsPanel')
const { useBriefing } = await import('../hooks/useBriefing')
const { useNotifications } = await import('../hooks/useNotifications')
const { AuthProvider } = await import('../contexts/AuthContext')

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  authMock.getSession.mockResolvedValue({
    data: { session: { access_token: 'test-token', user: { id: 'u1' } } },
  })
  authMock.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })

  // Default fetch responses
  fetchMock.mockImplementation((url: string) => {
    if (url.includes('/api/briefing')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ type: 'morning', content: 'Good morning! Today looks busy.' }),
      })
    }
    if (url.includes('/api/notifications')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ notifications: [] }),
      })
    }
    if (url.includes('/api/chat')) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ response: 'Hello', conversation_id: 'c1' }),
      })
    }
    return Promise.resolve({ ok: true, json: async () => ({}) })
  })

  // mock navigator.mediaDevices
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia: vi.fn() },
    configurable: true,
    writable: true,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderWithAuth(ui: React.ReactElement) {
  return render(
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  )
}

describe('MainLayout', () => {
  it('test_main_layout_renders_header', async () => {
    await act(async () => { renderWithAuth(<MainLayout><div>content</div></MainLayout>) })
    await waitFor(() => expect(screen.getByTestId('main-header')).toBeInTheDocument())
  })

  it('test_main_layout_renders_sidebar_on_desktop', async () => {
    await act(async () => { renderWithAuth(<MainLayout><div>content</div></MainLayout>) })
    await waitFor(() => expect(screen.getByTestId('main-sidebar')).toBeInTheDocument())
  })

  it('test_main_layout_renders_chat_area', async () => {
    await act(async () => { renderWithAuth(<MainLayout><div data-testid="chat-slot">chat</div></MainLayout>) })
    await waitFor(() => expect(screen.getByTestId('chat-slot')).toBeInTheDocument())
  })

  it('test_main_layout_renders_voice_bar', async () => {
    await act(async () => { renderWithAuth(<MainLayout><div>content</div></MainLayout>) })
    await waitFor(() => expect(screen.getByTestId('voice-bar')).toBeInTheDocument())
  })
})

describe('BriefingCard', () => {
  it('test_briefing_card_renders_content', async () => {
    await act(async () => { renderWithAuth(<BriefingCard />) })
    await waitFor(() => {
      expect(screen.getByTestId('briefing-content')).toBeInTheDocument()
    })
    expect(screen.getByText('Good morning! Today looks busy.')).toBeInTheDocument()
  })

  it('test_briefing_card_renders_loading_state', async () => {
    // Make fetch hang so we can see loading state
    fetchMock.mockImplementation(() => new Promise(() => {}))
    await act(async () => { renderWithAuth(<BriefingCard />) })
    expect(screen.getByTestId('briefing-loading')).toBeInTheDocument()
  })

  it('test_briefing_card_fetches_on_mount', async () => {
    await act(async () => { renderWithAuth(<BriefingCard />) })
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/api/briefing'),
        expect.any(Object),
      )
    })
  })
})

describe('NotificationsPanel', () => {
  it('test_notifications_panel_renders_notification_items', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/api/notifications')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            notifications: [
              { id: 'n1', type: 'reminder', title: 'Anniversary in 3 days', body: '', priority: 'high', status: 'pending' },
              { id: 'n2', type: 'conflict', title: 'Schedule conflict', body: '', priority: 'medium', status: 'pending' },
            ],
          }),
        })
      }
      return Promise.resolve({ ok: true, json: async () => ({}) })
    })

    await act(async () => { renderWithAuth(<NotificationsPanel />) })
    await waitFor(() => {
      expect(screen.getAllByTestId('notification-chip').length).toBeGreaterThan(0)
    })
  })

  it('test_notifications_panel_renders_empty_state', async () => {
    await act(async () => { renderWithAuth(<NotificationsPanel />) })
    await waitFor(() => {
      expect(screen.getByText('No alerts')).toBeInTheDocument()
    })
  })
})

describe('hooks', () => {
  it('test_use_briefing_fetches_morning_briefing', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter><AuthProvider>{children}</AuthProvider></MemoryRouter>
    )

    const { result } = renderHook(() => useBriefing(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('briefing'),
      expect.any(Object),
    )
  })

  it('test_use_notifications_fetches_pending_notifications', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter><AuthProvider>{children}</AuthProvider></MemoryRouter>
    )

    const { result } = renderHook(() => useNotifications(), { wrapper })

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('notifications'),
      expect.any(Object),
    )
  })
})
