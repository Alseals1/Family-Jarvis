import { api } from './client'

test('api.baseUrl defaults to localhost backend', () => {
  expect(api.baseUrl).toBe('http://localhost:8000')
})
