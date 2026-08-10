import { useNotifications } from '../../hooks/useNotifications'
import styles from './NotificationsPanel.module.css'

export default function NotificationsPanel() {
  const { notifications, loading, error } = useNotifications()

  if (loading) {
    return (
      <div className={styles.panel}>
        <span className={styles.title}>ALERTS</span>
        <div className={styles.loadingRow}>Loading...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.panel}>
        <span className={styles.title}>ALERTS</span>
        <p className={styles.error}>{error}</p>
      </div>
    )
  }

  if (notifications.length === 0) {
    return (
      <div className={styles.panel}>
        <span className={styles.title}>ALERTS</span>
        <p className={styles.emptyState}>No alerts</p>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <span className={styles.title}>ALERTS</span>
      <div className={styles.list}>
        {notifications.map(n => (
          <div
            key={n.id}
            className={`${styles.chip} ${styles[n.priority] ?? ''}`}
            data-testid="notification-chip"
          >
            <span className={styles.chipTitle}>{n.title}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
