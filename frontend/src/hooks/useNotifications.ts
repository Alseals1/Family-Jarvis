import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

interface Notification {
  id: string
  type: string
  title: string
  body: string
  priority: string
  status: string
  created_at?: string
}

interface UseNotificationsReturn {
  notifications: Notification[]
  loading: boolean
  error: string | null
}

export function useNotifications(): UseNotificationsReturn {
  const { session } = useAuth()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!session) return

    setLoading(true)
    api
      .get<{ notifications: Notification[] }>('/api/notifications', session.access_token)
      .then(data => {
        setNotifications(data.notifications ?? [])
        setError(null)
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load notifications')
      })
      .finally(() => setLoading(false))
  }, [session])

  return { notifications, loading, error }
}
