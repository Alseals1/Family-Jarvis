import styles from './HUDRing.module.css'

interface HUDRingProps {
  size?: 'sm' | 'md' | 'lg'
}

export default function HUDRing({ size = 'md' }: HUDRingProps) {
  return (
    <div
      className={`${styles.hudRing} ${styles[size]}`}
      aria-label="JARVIS"
      role="img"
    >
      <div className={styles.ring1} />
      <div className={styles.ring2} />
      <div className={styles.ring3} />
      <div className={styles.core} />
    </div>
  )
}
