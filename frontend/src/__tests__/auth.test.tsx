import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

// Mutable auth mock — tests mutate these functions before each render
const authMock = {
  signInWithPassword: vi.fn().mockResolvedValue({ data: { session: null, user: null }, error: null }),
  signOut: vi.fn().mockResolvedValue({}),
  getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
  onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
}

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({ auth: authMock })),
}))

// Import after mock is set up
const { AuthProvider, useAuth } = await import('../contexts/AuthContext')
const { default: LoginPage } = await import('../pages/LoginPage/LoginPage')
const { default: ProtectedRoute } = await import('../components/ProtectedRoute/ProtectedRoute')

beforeEach(() => {
  vi.clearAllMocks()
  authMock.signInWithPassword.mockResolvedValue({ data: { session: null, user: null }, error: null })
  authMock.signOut.mockResolvedValue({})
  authMock.getSession.mockResolvedValue({ data: { session: null } })
  authMock.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } })
})

function renderLoginPage(entries = ['/login']) {
  return render(
    <MemoryRouter initialEntries={entries}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('test_login_page_renders_email_input', async () => {
    await act(async () => { renderLoginPage() })
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  })

  it('test_login_page_renders_password_input', async () => {
    await act(async () => { renderLoginPage() })
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  })

  it('test_login_page_renders_submit_button', async () => {
    await act(async () => { renderLoginPage() })
    expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument()
  })

  it('test_login_page_shows_error_on_failed_auth', async () => {
    authMock.signInWithPassword.mockResolvedValue({
      data: { session: null, user: null },
      error: new Error('Invalid credentials'),
    })
    await act(async () => { renderLoginPage() })
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'bad@test.com' } })
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } })
      fireEvent.click(screen.getByRole('button', { name: /connect/i }))
    })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('test_login_page_calls_sign_in_on_submit', async () => {
    await act(async () => { renderLoginPage() })
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@test.com' } })
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret' } })
      fireEvent.click(screen.getByRole('button', { name: /connect/i }))
    })
    await waitFor(() => {
      expect(authMock.signInWithPassword).toHaveBeenCalledWith({ email: 'user@test.com', password: 'secret' })
    })
  })

  it('test_login_page_renders_hud_ring', async () => {
    await act(async () => { renderLoginPage() })
    expect(screen.getByRole('img', { name: 'JARVIS' })).toBeInTheDocument()
  })
})

describe('AuthContext', () => {
  it('test_auth_context_provides_session', async () => {
    const mockSession = { access_token: 'abc', user: { id: 'u1' } }
    authMock.getSession.mockResolvedValue({ data: { session: mockSession } })

    function SessionDisplay() {
      const { session } = useAuth()
      return <div>{session ? 'has-session' : 'no-session'}</div>
    }

    await act(async () => {
      render(
        <MemoryRouter>
          <AuthProvider>
            <SessionDisplay />
          </AuthProvider>
        </MemoryRouter>,
      )
    })

    await waitFor(() => {
      expect(screen.getByText('has-session')).toBeInTheDocument()
    })
  })

  it('test_auth_context_provides_sign_out', async () => {
    function SignOutButton() {
      const { signOut } = useAuth()
      return <button onClick={() => void signOut()}>Sign Out</button>
    }

    await act(async () => {
      render(
        <MemoryRouter>
          <AuthProvider>
            <SignOutButton />
          </AuthProvider>
        </MemoryRouter>,
      )
    })

    await act(async () => { fireEvent.click(screen.getByText('Sign Out')) })
    expect(authMock.signOut).toHaveBeenCalled()
  })
})

describe('ProtectedRoute', () => {
  it('test_protected_route_redirects_when_no_session', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <Routes>
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <div>Protected Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/login" element={<div>Login Page</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(container.textContent).toMatch(/Login Page/)
    })
  })

  it('test_protected_route_renders_children_when_session_exists', async () => {
    const mockSession = { access_token: 'abc', user: { id: 'u1' } }
    authMock.getSession.mockResolvedValue({ data: { session: mockSession } })

    await act(async () => {
      render(
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <div>Protected Content</div>
                  </ProtectedRoute>
                }
              />
              <Route path="/login" element={<div>Login Page</div>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>,
      )
    })

    await waitFor(() => {
      expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })
  })
})
