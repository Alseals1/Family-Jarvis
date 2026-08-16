import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { useAuth } from '../contexts/AuthContext'

export interface ConnectedCalendar {
  id: string
  member_id: string | null
  provider: string
  external_id: string
  name: string | null
  last_synced_at: string | null
}

interface CalendarStatus {
  family_id: string
  connected_calendars: ConnectedCalendar[]
}

interface ConnectResponse {
  oauth_url: string
}

interface SyncResponse {
  synced: number
  calendars?: number
}

interface UseCalendarReturn {
  calendars: ConnectedCalendar[]
  loading: boolean
  error: string | null
  syncing: boolean
  connecting: boolean
  /** Fetches the Google consent URL and navigates the browser to it. */
  connectGoogle: () => Promise<void>
  syncNow: () => Promise<void>
  refresh: () => Promise<void>
}

export function useCalendar(): UseCalendarReturn {
  const { session } = useAuth()
  const [calendars, setCalendars] = useState<ConnectedCalendar[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [connecting, setConnecting] = useState(false)

  const token = session?.access_token

  const refresh = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const data = await api.get<CalendarStatus>('/api/calendar/status', token)
      setCalendars(data.connected_calendars ?? [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load calendars')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const connectGoogle = useCallback(async () => {
    if (!token) return
    setConnecting(true)
    setError(null)
    try {
      const data = await api.get<ConnectResponse>('/api/calendar/connect/google', token)
      // Full navigation, not fetch: the consent screen is Google's page, and
      // the callback comes back as a browser redirect.
      window.location.assign(data.oauth_url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start Google sign-in')
      setConnecting(false)
    }
  }, [token])

  const syncNow = useCallback(async () => {
    if (!token) return
    setSyncing(true)
    setError(null)
    try {
      await api.post<SyncResponse>('/api/calendar/sync', {}, token)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed')
    } finally {
      setSyncing(false)
    }
  }, [token, refresh])

  return {
    calendars,
    loading,
    error,
    syncing,
    connecting,
    connectGoogle,
    syncNow,
    refresh,
  }
}

/** Human-readable copy for the ?reason= slugs the OAuth callback redirects with. */
export const OAUTH_REASON_MESSAGES: Record<string, string> = {
  access_denied: 'Google sign-in was cancelled. No calendar was connected.',
  invalid_state: 'That sign-in link expired. Please try connecting again.',
  missing_code_or_state: 'Google sent an incomplete response. Please try again.',
  encryption_not_configured:
    'Calendar encryption is not configured on the server. Set CALENDAR_ENCRYPTION_KEY.',
  token_exchange_failed: 'Google rejected the sign-in. Please try again.',
  calendar_list_failed: 'Connected, but your calendar list could not be read.',
  unknown_error: 'Something went wrong connecting your calendar.',
}
