import { useState, useCallback } from 'react'
import { api } from '../api/client'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface ChatResponse {
  response: string
  session_id?: string
}

interface UseChatReturn {
  messages: ChatMessage[]
  loading: boolean
  error: string | null
  /** Resolves with JARVIS's reply text, or null if the request failed. */
  sendMessage: (text: string, token?: string) => Promise<string | null>
  conversationId: string | null
}

export function useChat(): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)

  const sendMessage = useCallback(async (text: string, token?: string): Promise<string | null> => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
    }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    setError(null)

    try {
      const data = await api.post<ChatResponse>(
        '/api/chat',
        { message: text, session_id: conversationId },
        token,
      )
      if (data.session_id) {
        setConversationId(data.session_id)
      }
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response,
      }
      setMessages(prev => [...prev, assistantMsg])
      // Returned so voice callers can speak the reply. Without this they have
      // no handle on it and can only reach for the transcript.
      return data.response
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      return null
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  return { messages, loading, error, sendMessage, conversationId }
}
