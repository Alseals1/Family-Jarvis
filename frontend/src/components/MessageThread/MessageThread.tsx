import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../../hooks/useChat'
import MessageBubble from '../MessageBubble/MessageBubble'
import styles from './MessageThread.module.css'

interface MessageThreadProps {
  messages: ChatMessage[]
}

export default function MessageThread({ messages }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className={styles.thread} data-testid="message-thread">
        <div className={styles.emptyState}>
          <span className={styles.emptyText}>JARVIS is ready. How can I help?</span>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.thread} data-testid="message-thread">
      {messages.map(msg => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
