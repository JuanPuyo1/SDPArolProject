import type { ChatMessageData } from '../../components/ChatMessage'

/** Chat memory survives route navigation and browser restarts, but expires
 * after this long without a new message, and is cleared explicitly on
 * logout (see useAuth.tsx). */
const TTL_MS = 24 * 60 * 60 * 1000

export type PersistedChat = {
  sessionId: string
  machineSerial: string
  messages: ChatMessageData[]
  lastMessageAt: number
}

function storageKey(username: string): string {
  return `arol.chat.${username}`
}

/** Returns null if there's nothing stored, it's for a different machine, or
 * it's past the inactivity TTL -- callers should treat that the same as "no
 * prior conversation" and start fresh. */
export function loadPersistedChat(username: string, machineSerial: string): PersistedChat | null {
  try {
    const raw = localStorage.getItem(storageKey(username))
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedChat
    if (parsed.machineSerial !== machineSerial) return null
    if (Date.now() - parsed.lastMessageAt > TTL_MS) return null
    return parsed
  } catch {
    return null
  }
}

export function savePersistedChat(username: string, data: PersistedChat): void {
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(data))
  } catch {
    // best-effort -- a full/unavailable localStorage shouldn't break the chat
  }
}

export function clearPersistedChat(username: string): void {
  try {
    localStorage.removeItem(storageKey(username))
  } catch {
    // best-effort
  }
}
