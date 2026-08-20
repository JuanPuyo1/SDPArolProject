export type FocusSource = 'qr' | 'list' | 'link'

export type MachineFocus = {
  serialNumber: string
  machineId: string
  source: FocusSource
}

function storageKey(username: string): string {
  return `arol.focus.${username}`
}

export function loadMachineFocus(username: string): MachineFocus | null {
  try {
    const raw = sessionStorage.getItem(storageKey(username))
    if (!raw) return null
    const parsed = JSON.parse(raw) as MachineFocus
    if (!parsed.serialNumber || !parsed.machineId) return null
    return parsed
  } catch {
    return null
  }
}

export function saveMachineFocus(username: string, focus: MachineFocus): void {
  try {
    sessionStorage.setItem(storageKey(username), JSON.stringify(focus))
  } catch {
    // best-effort — a full/unavailable sessionStorage shouldn't break navigation
  }
}

export function clearMachineFocus(username: string): void {
  try {
    sessionStorage.removeItem(storageKey(username))
  } catch {
    // best-effort
  }
}
