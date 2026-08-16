import { useAuth } from '../contexts/AuthContext'
import { useChat } from '../hooks/useChat'
import MessageThread from '../components/MessageThread/MessageThread'
import ThinkingIndicator from '../components/ThinkingIndicator/ThinkingIndicator'
import ChatInput from '../components/ChatInput/ChatInput'
import styles from './Chat.module.css'

export default function Chat() {
  const { session } = useAuth()
  const { messages, loading, error, sendMessage } = useChat()

  function handleSend(text: string) {
    void sendMessage(text, session?.access_token)
  }

  return (
    <div className={styles.chatPage} data-testid="chat-page">
      <MessageThread messages={messages} />
      {loading && <ThinkingIndicator />}
      {error && (
        <div style={{
          margin: '8px 16px',
          padding: '8px 12px',
          background: '#1a0a0a',
          border: '1px solid var(--color-error, #ff4466)',
          borderRadius: '4px',
          color: 'var(--color-error, #ff4466)',
          fontSize: '0.8rem',
          fontFamily: 'var(--font-mono, monospace)',
        }}>
          {error}
        </div>
      )}
      <ChatInput onSubmit={handleSend} disabled={loading} />
    </div>
  )
}
