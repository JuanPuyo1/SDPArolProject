/** Extract a machine serial or machineId from a QR payload (URL or bare id). */
export function parseMachineIdFromQr(raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null

  try {
    const url = new URL(trimmed, window.location.origin)
    const match = url.pathname.match(/\/m\/([^/]+)\/?$/i)
    if (match?.[1]) {
      return decodeURIComponent(match[1])
    }
  } catch {
    // not a URL — fall through to bare-id handling
  }

  if (/^[A-Za-z0-9._-]+$/.test(trimmed)) {
    return trimmed
  }

  return null
}
