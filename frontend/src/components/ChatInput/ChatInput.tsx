import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import styles from './ChatInput.module.css'

interface ChatInputProps {
  onSubmit: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function ChatInput({ onSubmit, disabled = false, placeholder = 'Ask JARVIS...' }: ChatInputProps) {
  const [value, setValue] = useState('')

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !disabled) {
        onSubmit(value.trim())
        setValue('')
      }
    }
  }

  function handleSubmit() {
    if (value.trim() && !disabled) {
      onSubmit(value.trim())
      setValue('')
    }
  }

  return (
    <div className={styles.container}>
      <textarea
        className={styles.textarea}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        rows={1}
        aria-label="Message input"
      />
      <button
        className={styles.sendBtn}
        onClick={handleSubmit}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        type="button"
      >
        Send
      </button>
    </div>
  )
}
