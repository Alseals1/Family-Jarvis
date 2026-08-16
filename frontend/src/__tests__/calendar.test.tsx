/**
 * Calendar connection UI tests.
 *
 * Covers the page that was missing entirely — there was no way to connect a
 * calendar from the app — and the OAuth outcome banners the backend redirects
 * back with.
 */

import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const mockSession = { access_token: 'jwt-abc', user: { id: 'u1' } }

vi.mock('../contexts/AuthContext', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../contexts/AuthContext')
  return {
    ...actual,
    useAuth: () => ({ session: mockSession, signOut: vi.fn(), loading: false }),
  }
})

const { default: CalendarPage } = await import('../pages/Calendar')

let fetchMock: ReturnType<typeof vi.fn>
let assignMock: ReturnType<typeof vi.fn>

const CAL = {
  id: 'cal-1',
  member_id: 'm1',
  provider: 'google',
  external_id: 'primary',
  name: 'Work Calendar',
  last_synced_at: null,
}

function statusResponse(calendars: unknown[]) {
  return { ok: true, json: async () => ({ family_id: 'f1', connected_calendars: calendars }) }
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/calendar" element={<CalendarPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(statusResponse([]))
  vi.stubGlobal('fetch', fetchMock)

  // Replace only the navigation call — stubbing all of `window` would take the
  // DOM with it and every render would fail.
  assignMock = vi.fn()
  Object.defineProperty(window, 'location', {
    configurable: true,
    writable: true,
    value: { ...window.location, assign: assignMock },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('Calendar page — empty state', () => {
  it('test_shows_connect_prompt_when_no_calendars', async () => {
    await act(async () => { renderAt('/calendar') })
    expect(await screen.findByTestId('calendar-empty')).toBeInTheDocument()
    expect(screen.getByText(/Connect Google Calendar/i)).toBeInTheDocument()
  })

  it('test_states_read_only_guarantee', async () => {
    await act(async () => { renderAt('/calendar') })
    // A product constraint, stated in the UI: JARVIS never writes to calendars.
    expect(screen.getByText(/never creates, edits, or deletes/i)).toBeInTheDocument()
  })

  it('test_connect_button_requests_oauth_url', async () => {
    fetchMock
      .mockResolvedValueOnce(statusResponse([]))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ oauth_url: 'https://accounts.google.com/o/oauth2/v2/auth?x=1' }),
      })

    await act(async () => { renderAt('/calendar') })
    await act(async () => {
      fireEvent.click(screen.getByText(/Connect Google Calendar/i))
    })

    const urls = fetchMock.mock.calls.map(c => c[0] as string)
    expect(urls.some(u => u.includes('/api/calendar/connect/google'))).toBe(true)
  })

  it('test_connect_navigates_browser_to_google', async () => {
    fetchMock
      .mockResolvedValueOnce(statusResponse([]))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ oauth_url: 'https://accounts.google.com/o/oauth2/v2/auth?x=1' }),
      })

    await act(async () => { renderAt('/calendar') })
    await act(async () => {
      fireEvent.click(screen.getByText(/Connect Google Calendar/i))
    })

    // Must be a real navigation — the consent screen cannot be fetched.
    await waitFor(() => {
      expect(assignMock).toHaveBeenCalledWith('https://accounts.google.com/o/oauth2/v2/auth?x=1')
    })
  })
})

describe('Calendar page — connected state', () => {
  it('test_lists_connected_calendars', async () => {
    fetchMock.mockResolvedValue(statusResponse([CAL]))
    await act(async () => { renderAt('/calendar') })

    expect(await screen.findByTestId('calendar-list')).toBeInTheDocument()
    expect(screen.getByText('Work Calendar')).toBeInTheDocument()
  })

  it('test_shows_never_synced_for_null_timestamp', async () => {
    fetchMock.mockResolvedValue(statusResponse([CAL]))
    await act(async () => { renderAt('/calendar') })

    expect(await screen.findByText(/never synced/i)).toBeInTheDocument()
  })

  it('test_sync_button_posts_to_sync_endpoint', async () => {
    fetchMock.mockResolvedValue(statusResponse([CAL]))
    await act(async () => { renderAt('/calendar') })

    await act(async () => {
      fireEvent.click(await screen.findByText(/Sync now/i))
    })

    const called = fetchMock.mock.calls.some(
      ([url, init]) =>
        (url as string).includes('/api/calendar/sync') &&
        (init as RequestInit)?.method === 'POST',
    )
    expect(called).toBe(true)
  })

  it('test_status_request_sends_bearer_token', async () => {
    fetchMock.mockResolvedValue(statusResponse([CAL]))
    await act(async () => { renderAt('/calendar') })

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [, init] = fetchMock.mock.calls[0]
    expect((init as { headers: Record<string, string> }).headers.Authorization)
      .toBe('Bearer jwt-abc')
  })
})

describe('OAuth return banners', () => {
  it('test_success_banner_on_connected_1', async () => {
    fetchMock.mockResolvedValue(statusResponse([CAL]))
    await act(async () => { renderAt('/calendar?connected=1&count=2') })

    const banner = await screen.findByTestId('oauth-outcome')
    expect(banner).toHaveTextContent(/Connected 2 calendars/i)
  })

  it('test_success_banner_singular_for_one_calendar', async () => {
    fetchMock.mockResolvedValue(statusResponse([CAL]))
    await act(async () => { renderAt('/calendar?connected=1&count=1') })

    const banner = await screen.findByTestId('oauth-outcome')
    expect(banner).toHaveTextContent(/Connected 1 calendar\./i)
  })

  it('test_error_banner_for_access_denied', async () => {
    await act(async () => { renderAt('/calendar?connected=0&reason=access_denied') })

    const banner = await screen.findByTestId('oauth-outcome')
    expect(banner).toHaveTextContent(/cancelled/i)
  })

  it('test_error_banner_for_expired_state', async () => {
    await act(async () => { renderAt('/calendar?connected=0&reason=invalid_state') })

    const banner = await screen.findByTestId('oauth-outcome')
    expect(banner).toHaveTextContent(/expired/i)
  })

  it('test_unknown_reason_falls_back_to_generic_message', async () => {
    await act(async () => { renderAt('/calendar?connected=0&reason=something_new') })

    const banner = await screen.findByTestId('oauth-outcome')
    expect(banner).toHaveTextContent(/Something went wrong/i)
  })

  it('test_no_banner_without_oauth_params', async () => {
    await act(async () => { renderAt('/calendar') })
    expect(screen.queryByTestId('oauth-outcome')).not.toBeInTheDocument()
  })
})

describe('failure handling', () => {
  it('test_shows_error_when_status_request_fails', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500, statusText: 'Server Error' })
    await act(async () => { renderAt('/calendar') })

    expect(await screen.findByTestId('calendar-error')).toBeInTheDocument()
  })
})
