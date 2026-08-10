import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import App from './App'

vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    auth: {
      signInWithPassword: vi.fn(),
      signOut: vi.fn(),
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
  })),
}))

test('unauthenticated user sees login page at /', async () => {
  render(<App />)
  // ProtectedRoute redirects to /login; login page shows J.A.R.V.I.S. heading
  await screen.findByText('J.A.R.V.I.S.')
  expect(screen.getByText('J.A.R.V.I.S.')).toBeInTheDocument()
})
