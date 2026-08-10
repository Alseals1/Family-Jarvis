import { useAuth } from '../contexts/AuthContext'
import { useChat } from '../hooks/useChat'
import MessageThread from '../components/MessageThread/MessageThread'
import ThinkingIndicator from '../components/ThinkingIndicator/ThinkingIndicator'
import ChatInput from '../components/ChatInput/ChatInput'
import styles from './Chat.module.css'

export default function Chat() {
  const { session } = useAuth()
  const { messages, loading, sendMessage } = useChat()

  function handleSend(text: string) {
    void sendMessage(text, session?.access_token)
  }

  return (
    <div className={styles.chatPage} data-testid="chat-page">
      <MessageThread messages={messages} />
      {loading && <ThinkingIndicator />}
      <ChatInput onSubmit={handleSend} disabled={loading} />
    </div>
  )
}
