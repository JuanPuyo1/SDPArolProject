import type { ChatMessageData } from '../../components/ChatMessage'

/** Same inactivity TTL as the per-machine chat (see chatStorage.ts). */
const TTL_MS = 24 * 60 * 60 * 1000

export type PersistedFleetChat = {
  // Server-assigned LangGraph thread id -- null until the first reply.
  sessionId: string | null
  messages: ChatMessageData[]
  lastMessageAt: number
}

function storageKey(username: string): string {
  return `arol.fleetchat.${username}`
}

function isExpired(state: PersistedFleetChat): boolean {
  return Date.now() - state.lastMessageAt > TTL_MS
}

/** One running conversation per user (no session tabs, unlike the
 * per-machine chatbot) -- this is a lightweight company-info FAQ widget, not
 * a primary workspace. Returns null if there's nothing stored or it's past
 * the inactivity TTL; callers should treat that as "start fresh". */
export function loadPersistedFleetChat(username: string): PersistedFleetChat | null {
  try {
    const raw = localStorage.getItem(storageKey(username))
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedFleetChat
    if (isExpired(parsed)) return null
    return parsed
  } catch {
    return null
  }
}

export function savePersistedFleetChat(username: string, state: PersistedFleetChat): void {
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(state))
  } catch {
    // best-effort -- a full/unavailable localStorage shouldn't break the chat
  }
}
