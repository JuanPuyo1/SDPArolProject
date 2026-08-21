import type { ChatMessageData } from '../../components/ChatMessage'

/** Each session's memory survives route navigation and browser restarts, but
 * expires after this long without a new message in it, and is cleared
 * explicitly on logout (see useAuth.tsx). */
const TTL_MS = 24 * 60 * 60 * 1000

/** Up to this many conversations can be open at once for a user. */
export const MAX_SESSIONS = 3

export type PersistedSession = {
  id: string
  // Server-assigned LangGraph thread id -- null until this session's first
  // message gets a reply (see useChat.ts's resumeSessionId).
  sessionId: string | null
  messages: ChatMessageData[]
  lastMessageAt: number
}

export type PersistedChatState = {
  machineSerial: string
  activeSessionId: string
  sessions: PersistedSession[]
}

function storageKeyPrefix(username: string): string {
  return `arol.chat.${username}.`
}

function storageKey(username: string, machineSerial: string): string {
  return `${storageKeyPrefix(username)}${machineSerial}`
}

function isExpired(session: PersistedSession): boolean {
  return Date.now() - session.lastMessageAt > TTL_MS
}

/** Returns null if there's nothing stored, it's for a different machine, or
 * every session is past the inactivity TTL -- callers should treat that the
 * same as "no prior conversations" and start fresh. Individually-expired
 * sessions are silently dropped rather than expiring the whole set. */
export function loadPersistedChat(username: string, machineSerial: string): PersistedChatState | null {
  try {
    const raw = localStorage.getItem(storageKey(username, machineSerial))
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedChatState
    if (parsed.machineSerial !== machineSerial) return null
    const sessions = parsed.sessions.filter((s) => !isExpired(s))
    if (sessions.length === 0) return null
    const activeSessionId = sessions.some((s) => s.id === parsed.activeSessionId)
      ? parsed.activeSessionId
      : sessions[0].id
    return { machineSerial, activeSessionId, sessions }
  } catch {
    return null
  }
}

export function savePersistedChat(username: string, state: PersistedChatState): void {
  try {
    localStorage.setItem(storageKey(username, state.machineSerial), JSON.stringify(state))
  } catch {
    // best-effort -- a full/unavailable localStorage shouldn't break the chat
  }
}

/** Clears every machine's persisted chat for this user (e.g. on logout). */
export function clearPersistedChat(username: string): void {
  try {
    const prefix = storageKeyPrefix(username)
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith(prefix)) localStorage.removeItem(key)
    }
  } catch {
    // best-effort
  }
}
