import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Button from '../components/Button/Button'
import { useCalendar, OAUTH_REASON_MESSAGES } from '../hooks/useCalendar'
import styles from './Calendar.module.css'

function formatSynced(iso: string | null): string {
  if (!iso) return 'never synced'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'never synced'
  return `synced ${d.toLocaleString()}`
}

export default function Calendar() {
  const {
    calendars,
    loading,
    error,
    syncing,
    connecting,
    connectGoogle,
    syncNow,
    refresh,
  } = useCalendar()

  // The OAuth callback lands back here with ?connected=1 or ?connected=0&reason=
  const [searchParams, setSearchParams] = useSearchParams()
  const [outcome, setOutcome] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    const connected = searchParams.get('connected')
    if (connected === null) return

    if (connected === '1') {
      const count = Number(searchParams.get('count') ?? 0)
      setOutcome({
        ok: true,
        text: `Connected ${count} calendar${count === 1 ? '' : 's'}. Sync to pull in events.`,
      })
      void refresh()
    } else {
      const reason = searchParams.get('reason') ?? 'unknown_error'
      setOutcome({
        ok: false,
        text: OAUTH_REASON_MESSAGES[reason] ?? OAUTH_REASON_MESSAGES.unknown_error,
      })
    }

    // Clear the params so a refresh does not replay the banner.
    setSearchParams({}, { replace: true })
  }, [searchParams, setSearchParams, refresh])

  const hasCalendars = calendars.length > 0

  return (
    <div className={styles.calendarPage} data-testid="calendar-page">
      <div className={styles.header}>
        <h1 className={styles.title}>Calendars</h1>
        {hasCalendars && (
          <span className={styles.subtitle}>
            {calendars.length} connected
          </span>
        )}
      </div>

      {outcome && (
        <div
          role="status"
          data-testid="oauth-outcome"
          className={`${styles.banner} ${outcome.ok ? styles.bannerSuccess : styles.bannerError}`}
        >
          {outcome.text}
        </div>
      )}

      {error && (
        <div role="alert" data-testid="calendar-error" className={`${styles.banner} ${styles.bannerError}`}>
          {error}
        </div>
      )}

      {loading && <div className={styles.loading}>LOADING CALENDARS...</div>}

      {!loading && !hasCalendars && (
        <div className={styles.empty} data-testid="calendar-empty">
          <p className={styles.emptyTitle}>NO CALENDARS CONNECTED</p>
          <p className={styles.emptyText}>
            Connect a Google Calendar so JARVIS can see your family&apos;s schedule,
            spot conflicts, and find free evenings.
          </p>
          <Button onClick={() => void connectGoogle()} disabled={connecting}>
            {connecting ? 'Opening Google...' : 'Connect Google Calendar'}
          </Button>
        </div>
      )}

      {!loading && hasCalendars && (
        <>
          <ul className={styles.list} data-testid="calendar-list">
            {calendars.map(cal => (
              <li key={cal.id} className={styles.calendarRow}>
                <span className={styles.calendarName}>{cal.name ?? cal.external_id}</span>
                <span className={styles.calendarMeta}>
                  {cal.provider} · {formatSynced(cal.last_synced_at)}
                </span>
              </li>
            ))}
          </ul>

          <div className={styles.actions}>
            <Button onClick={() => void syncNow()} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync now'}
            </Button>
            <Button variant="secondary" onClick={() => void connectGoogle()} disabled={connecting}>
              {connecting ? 'Opening Google...' : 'Connect another'}
            </Button>
          </div>
        </>
      )}

      <p className={styles.readOnlyNote}>
        Read-only access. JARVIS never creates, edits, or deletes calendar events.
      </p>
    </div>
  )
}
