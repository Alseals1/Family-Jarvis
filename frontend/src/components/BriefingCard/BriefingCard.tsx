import { useBriefing } from '../../hooks/useBriefing'
import Card from '../Card/Card'
import styles from './BriefingCard.module.css'

export default function BriefingCard() {
  const { briefing, loading, error } = useBriefing()

  if (loading) {
    return (
      <Card>
        <div className={styles.header} data-testid="briefing-loading">
          <span className={styles.title}>MORNING BRIEFING</span>
        </div>
        <div className={styles.skeleton}>
          <div className={styles.skeletonLine} />
          <div className={styles.skeletonLine} style={{ width: '80%' }} />
          <div className={styles.skeletonLine} style={{ width: '60%' }} />
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <div className={styles.header}>
          <span className={styles.title}>MORNING BRIEFING</span>
        </div>
        <p className={styles.error}>{error}</p>
      </Card>
    )
  }

  return (
    <Card>
      <div className={styles.header}>
        <span className={styles.title}>MORNING BRIEFING</span>
      </div>
      <p className={styles.content} data-testid="briefing-content">
        {briefing?.content ?? 'No briefing available.'}
      </p>
    </Card>
  )
}
