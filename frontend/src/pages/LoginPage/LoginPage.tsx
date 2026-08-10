import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import HUDRing from '../../components/HUDRing/HUDRing'
import Button from '../../components/Button/Button'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const { error: authError } = await signIn(email, password)
    setLoading(false)
    if (authError) {
      setError(authError.message)
    } else {
      navigate('/')
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <HUDRing size="lg" />
        <h1 className={styles.title}>J.A.R.V.I.S.</h1>
        <p className={styles.subtitle}>Family Chief of Staff</p>
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>
              Email
            </label>
            <input
              id="email"
              type="email"
              className={styles.input}
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="your@email.com"
              autoComplete="email"
              required
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>
              Password
            </label>
            <input
              id="password"
              type="password"
              className={styles.input}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? 'Connecting...' : 'Connect'}
          </Button>
        </form>
      </div>
    </div>
  )
}
