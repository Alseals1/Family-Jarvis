import styles from './ThinkingIndicator.module.css'

export default function ThinkingIndicator() {
  return (
    <div className={styles.container} aria-label="JARVIS is thinking" role="status">
      <span className={styles.dot} />
      <span className={styles.dot} />
      <span className={styles.dot} />
    </div>
  )
}
