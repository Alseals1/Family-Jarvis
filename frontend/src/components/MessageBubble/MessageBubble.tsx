import type { ChatMessage } from '../../hooks/useChat'
import styles from './MessageBubble.module.css'

interface MessageBubbleProps {
  message: ChatMessage
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  return (
    <div
      className={`${styles.wrapper} ${isUser ? styles.userWrapper : styles.jarvisWrapper}`}
      data-role={message.role}
    >
      {!isUser && (
        <span className={styles.label}>JARVIS</span>
      )}
      <div
        className={`${styles.bubble} ${isUser ? styles.userBubble : styles.jarvisBubble}`}
      >
        <p className={styles.content}>{message.content}</p>
      </div>
    </div>
  )
}
