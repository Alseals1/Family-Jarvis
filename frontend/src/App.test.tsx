import { render, screen } from '@testing-library/react'
import App from './App'

test('renders home page at /', () => {
  render(<App />)
  expect(screen.getByTestId('home-page')).toBeInTheDocument()
})
