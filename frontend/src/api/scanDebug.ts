const DEBUG_KEY = 'arol.scan.debug'
const MAX_ENTRIES = 20

export function logScanDebug(message: string): void {
  const entry = `${new Date().toISOString()} ${message}`
  try {
    const prev = JSON.parse(sessionStorage.getItem(DEBUG_KEY) || '[]') as string[]
    sessionStorage.setItem(DEBUG_KEY, JSON.stringify([entry, ...prev].slice(0, MAX_ENTRIES)))
  } catch {
    // best-effort
  }
  if (import.meta.env.DEV) {
    console.info('[scan]', message)
  }
}

export function readScanDebugLog(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(DEBUG_KEY) || '[]') as string[]
  } catch {
    return []
  }
}

export function clearScanDebugLog(): void {
  try {
    sessionStorage.removeItem(DEBUG_KEY)
  } catch {
    // best-effort
  }
}
