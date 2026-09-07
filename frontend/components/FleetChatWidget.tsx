import { useCallback, useEffect, useRef, useState } from 'react'
import type { SyntheticEvent } from 'react'
import ChatMessage from './ChatMessage'
import type { ChatMessageData } from './ChatMessage'
import { useAuth } from '../src/hooks/useAuth'
import { useFleetChatStream } from '../src/hooks/useFleetChat'
import { loadPersistedFleetChat, savePersistedFleetChat } from '../src/api/fleetChatStorage'
import './FleetChatWidget.css'

function buildWelcomeMessage(): ChatMessageData {
  return {
    id: 'welcome',
    role: 'assistant',
    text:
      "Hi, I'm the AROL fleet assistant. Ask me about the machines your company owns, " +
      'their models, your company profile, or who else at your company uses this platform.',
    attachments: [],
  }
}

type FleetState = {
  messages: ChatMessageData[]
  sessionId: string | null
}

function initialState(): FleetState {
  return { messages: [buildWelcomeMessage()], sessionId: null }
}

export default function FleetChatWidget() {
  const { user } = useAuth()
  const [expanded, setExpanded] = useState(false)
  const [state, setState] = useState<FleetState>(initialState)
  const [draftText, setDraftText] = useState('')
  const restoredForRef = useRef<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Mirrors `state`, but updated synchronously (not via a useEffect, which
  // only runs after the next commit -- too late for handleSubmit's `finally`
  // block, which needs the just-computed value immediately). Same pattern as
  // ChatbotPage.tsx's chatStateRef.
  const stateRef = useRef<FleetState>(state)

  const updateState = useCallback(
    (updater: FleetState | ((prev: FleetState) => FleetState)) => {
      const next = typeof updater === 'function' ? updater(stateRef.current) : updater
      stateRef.current = next
      setState(next)
    },
    [],
  )

  const updateMessages = useCallback(
    (updater: (prev: ChatMessageData[]) => ChatMessageData[]) => {
      updateState((prev) => ({ ...prev, messages: updater(prev.messages) }))
    },
    [updateState],
  )

  const persist = useCallback(() => {
    if (!user) return
    savePersistedFleetChat(user.username, {
      sessionId: stateRef.current.sessionId,
      messages: stateRef.current.messages,
      lastMessageAt: Date.now(),
    })
  }, [user])

  const { isStreaming, error, sendMessage, resumeSessionId } = useFleetChatStream({
    onSessionIdChange: (sessionId) => {
      updateState((prev) => ({ ...prev, sessionId }))
      persist()
    },
  })

  // Restores this user's fleet-chat conversation (if any, not past the 24h
  // inactivity TTL) once known -- mirrors ChatbotPage's restore-on-mount
  // effect for the per-machine chat.
  useEffect(() => {
    if (!user) return
    if (restoredForRef.current === user.username) return
    restoredForRef.current = user.username

    const persisted = loadPersistedFleetChat(user.username)
    if (persisted?.messages.length) {
      updateState({ messages: persisted.messages, sessionId: persisted.sessionId })
      resumeSessionId(persisted.sessionId)
    }
  }, [user, resumeSessionId, updateState])

  async function handleSubmit(event: SyntheticEvent) {
    event.preventDefault()
    const userText = draftText.trim()
    if (!userText || isStreaming) return

    const assistantId = `fleet-reply-${Date.now()}`
    updateMessages((prev) => [
      ...prev,
      { id: `fleet-msg-${Date.now()}`, role: 'user', text: userText, attachments: [] },
      { id: assistantId, role: 'assistant', text: '', attachments: [], thinkingSteps: [] },
    ])
    setDraftText('')

    try {
      const reply = await sendMessage(userText, {
        onToken: (_token, fullText) => {
          updateMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, text: fullText } : m)),
          )
        },
        onThinkingSteps: (steps) => {
          updateMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, thinkingSteps: steps } : m)),
          )
        },
      })
      if (!reply) {
        updateMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, text: 'No response received.' } : m,
          ),
        )
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Fleet chat request failed.'
      updateMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, text: message } : m)))
    } finally {
      persist()
    }
  }

  return (
    <div className={`fleet-chat${expanded ? ' fleet-chat--expanded' : ''}`}>
      <button
        type="button"
        className="fleet-chat__toggle"
        onClick={() => setExpanded((prev) => !prev)}
        aria-expanded={expanded}
      >
        <span className="fleet-chat__toggle-title">Ask about your company's fleet</span>
        <span className="fleet-chat__toggle-icon" aria-hidden="true">
          {expanded ? '−' : '+'}
        </span>
      </button>

      {expanded && (
        <div className="fleet-chat__panel">
          {error && <p className="fleet-chat__error">{error}</p>}

          <div className="fleet-chat__messages">
            {state.messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
          </div>

          <form className="fleet-chat__composer" onSubmit={handleSubmit}>
            <div
              role="presentation"
              onClick={() => textareaRef.current?.focus()}
              className="fleet-chat__input-row"
            >
              <textarea
                ref={textareaRef}
                className="fleet-chat__textarea"
                placeholder="Ask about your machines, models, company or teammates…"
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void handleSubmit(e)
                  }
                }}
                rows={1}
                disabled={isStreaming}
              />
              <button
                type="submit"
                className="fleet-chat__send"
                disabled={isStreaming || !draftText.trim()}
                aria-label="Send message"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
