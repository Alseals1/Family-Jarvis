import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

interface Briefing {
  type: string
  content: string
  generated_at?: string
}

interface UseBriefingReturn {
  briefing: Briefing | null
  loading: boolean
  error: string | null
}

export function useBriefing(): UseBriefingReturn {
  const { session } = useAuth()
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!session) return

    setLoading(true)
    api
      .get<Briefing>('/api/briefing?type=morning', session.access_token)
      .then(data => {
        setBriefing(data)
        setError(null)
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load briefing')
      })
      .finally(() => setLoading(false))
  }, [session])

  return { briefing, loading, error }
}
