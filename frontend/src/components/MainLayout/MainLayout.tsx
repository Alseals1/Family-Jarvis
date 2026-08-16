import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import BriefingCard from '../BriefingCard/BriefingCard'
import NotificationsPanel from '../NotificationsPanel/NotificationsPanel'
import MicButton from '../MicButton/MicButton'
import { useVoiceConversation } from '../../hooks/useVoiceConversation'
import { useChat } from '../../hooks/useChat'
import styles from './MainLayout.module.css'

interface MainLayoutProps {
  children: ReactNode
}

export default function MainLayout({ children }: MainLayoutProps) {
  const { session, signOut } = useAuth()
  const { messages, sendMessage } = useChat()
  const { voiceState, isAvailable, handleMicPress } = useVoiceConversation({
    sendMessage,
    token: session?.access_token,
  })

  // messages is used for context but we don't need to display it here (Chat page does)
  void messages

  return (
    <div className={styles.layout} data-testid="main-layout">
      {/* Header */}
      <header className={styles.header} data-testid="main-header">
        <div className={styles.headerLeft}>
          <span className={styles.logoText}>J.A.R.V.I.S.</span>
          <span className={styles.statusDot} aria-hidden="true" />
          <span className={styles.statusText}>ONLINE</span>
        </div>
        <div className={styles.headerRight}>
          <nav className={styles.nav} aria-label="Main">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
              }
            >
              Chat
            </NavLink>
            <NavLink
              to="/calendar"
              className={({ isActive }) =>
                isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink
              }
            >
              Calendars
            </NavLink>
          </nav>
          <button
            className={styles.signOutBtn}
            onClick={() => void signOut()}
            type="button"
            aria-label="Sign out"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div className={styles.grid}>
        {/* Sidebar */}
        <aside className={styles.sidebar} data-testid="main-sidebar">
          <BriefingCard />
          <NotificationsPanel />
        </aside>

        {/* Content */}
        <main className={styles.main} data-testid="main-content">
          {children}
        </main>
      </div>

      {/* Footer / Voice bar */}
      <footer className={styles.footer} data-testid="voice-bar">
        <MicButton
          voiceState={voiceState}
          onPress={() => void handleMicPress()}
          isAvailable={isAvailable}
        />
        <span className={styles.voiceStatus}>
          {voiceState === 'idle' && 'Ready'}
          {voiceState === 'recording' && 'Listening...'}
          {voiceState === 'processing' && 'Processing...'}
          {voiceState === 'speaking' && 'JARVIS speaking...'}
        </span>
      </footer>
    </div>
  )
}
