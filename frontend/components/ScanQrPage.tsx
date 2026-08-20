import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { fetchMachine } from '../src/api/machines'
import { parseMachineIdFromQr } from '../src/api/qrMachineId'
import { clearScanDebugLog, logScanDebug, readScanDebugLog } from '../src/api/scanDebug'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import './SelectMachinePage.css'
import './ScanQrPage.css'

const READER_ID = 'qr-reader'

type ScanPhase =
  | 'idle'
  | 'loading-module'
  | 'camera-starting'
  | 'scanning'
  | 'resolving'
  | 'success'
  | 'error'

function finishScanInOpener(): boolean {
  if (!window.opener || window.opener.closed) return false
  try {
    window.opener.location.assign('/machine')
    window.close()
    return true
  } catch (err: unknown) {
    logScanDebug(
      `opener redirect failed: ${err instanceof Error ? err.message : 'unknown error'}`,
    )
    return false
  }
}

export default function ScanQrPage() {
  const { setFocusFromMachine } = useActiveMachine()
  const navigate = useNavigate()
  const [paste, setPaste] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<ScanPhase>('idle')
  const [debugLog, setDebugLog] = useState<string[]>(() => readScanDebugLog())
  const [openedAsPopup] = useState(() => Boolean(window.opener))

  const readerId = READER_ID
  const scannerRef = useRef<{ stop: () => Promise<void>; clear: () => void } | null>(null)
  const resolvingRef = useRef(false)
  const cameraActiveRef = useRef(false)

  const refreshDebugLog = useCallback(() => {
    setDebugLog(readScanDebugLog())
  }, [])

  const appendDebug = useCallback(
    (message: string) => {
      logScanDebug(message)
      refreshDebugLog()
    },
    [refreshDebugLog],
  )

  useEffect(() => {
    appendDebug(`page mount (popup=${openedAsPopup}, secure=${window.isSecureContext})`)
    return () => {
      appendDebug('page unmount')
      if (cameraActiveRef.current && scannerRef.current) {
        void scannerRef.current.stop().catch(() => undefined)
        scannerRef.current.clear()
        scannerRef.current = null
        cameraActiveRef.current = false
      }
    }
  }, [appendDebug, openedAsPopup])

  const stopCamera = useCallback(async () => {
    if (!scannerRef.current) return
    try {
      await scannerRef.current.stop()
    } catch {
      // camera may already be stopped
    }
    scannerRef.current.clear()
    scannerRef.current = null
    cameraActiveRef.current = false
    setPhase('idle')
    appendDebug('camera stopped')
  }, [appendDebug])

  const resolveIdentifier = useCallback(
    async (raw: string) => {
      if (resolvingRef.current) return
      const identifier = parseMachineIdFromQr(raw)
      if (!identifier) {
        setError('Could not read a machine id from that QR code.')
        setPhase('error')
        appendDebug(`parse failed: ${raw.slice(0, 120)}`)
        return
      }

      resolvingRef.current = true
      setPhase('resolving')
      setError(null)
      appendDebug(`resolve start: ${identifier}`)

      try {
        if (cameraActiveRef.current) {
          await stopCamera()
        }
        const machine = await fetchMachine(identifier)
        setFocusFromMachine(machine, 'qr')
        setPhase('success')
        appendDebug(`resolve ok: ${machine.serialNumber}`)

        if (finishScanInOpener()) {
          return
        }

        navigate('/machine', { replace: true })
      } catch (err: unknown) {
        resolvingRef.current = false
        const message = err instanceof Error ? err.message : 'Could not open this machine.'
        setError(message)
        setPhase('error')
        appendDebug(`resolve error: ${message}`)
      }
    },
    [appendDebug, navigate, setFocusFromMachine, stopCamera],
  )

  const startCamera = useCallback(async () => {
    if (cameraActiveRef.current || phase === 'loading-module' || phase === 'camera-starting') {
      return
    }

    setError(null)
    setPhase('loading-module')
    appendDebug('loading html5-qrcode module')

    try {
      const { Html5Qrcode } = await import('html5-qrcode')
      setPhase('camera-starting')
      appendDebug('starting camera')

      const scanner = new Html5Qrcode(readerId)
      scannerRef.current = scanner

      await scanner.start(
        { facingMode: 'environment' },
        { fps: 8, qrbox: { width: 240, height: 240 } },
        (decoded) => {
          appendDebug(`qr decoded: ${decoded.slice(0, 80)}`)
          void resolveIdentifier(decoded)
        },
        () => undefined,
      )

      cameraActiveRef.current = true
      setPhase('scanning')
      appendDebug('camera scanning')
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Camera is unavailable on this device.'
      setError(
        `${message} Paste the QR URL, upload a photo, or open this page over HTTPS if you need the live camera.`,
      )
      setPhase('error')
      appendDebug(`camera error: ${message}`)
      scannerRef.current = null
      cameraActiveRef.current = false
    }
  }, [appendDebug, phase, readerId, resolveIdentifier])

  async function handlePaste(event: FormEvent) {
    event.preventDefault()
    await resolveIdentifier(paste)
  }

  async function handleFile(file: File | undefined) {
    if (!file) return
    setError(null)
    setPhase('loading-module')
    appendDebug(`file scan: ${file.name}`)

    try {
      if (cameraActiveRef.current) {
        await stopCamera()
      }
      const { Html5Qrcode } = await import('html5-qrcode')
      const scanner = new Html5Qrcode(readerId)
      const decoded = await scanner.scanFile(file, true)
      scanner.clear()
      await resolveIdentifier(decoded)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not read that image.'
      setError(message)
      setPhase('error')
      appendDebug(`file error: ${message}`)
    }
  }

  return (
    <div className="scan-qr">
      <header className="scan-qr__header">
        <div className="select-machine__eyebrow">QR access</div>
        <h1 className="select-machine__title">Scan a machine QR</h1>
        <p className="select-machine__lead">
          {openedAsPopup
            ? 'Scanning in a separate tab keeps the main app stable. When a code is read, this tab will close and the main tab opens the machine.'
            : 'Point the camera at the code on the machine, or paste the URL / upload a photo.'}
        </p>
        <div className="scan-qr__actions">
          <Link to="/select" className="btn btn--ghost">
            Back to machine list
          </Link>
          {!openedAsPopup && (
            <a
              href="/scan"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn--ghost"
            >
              Open in new tab
            </a>
          )}
        </div>
      </header>

      <div className="scan-qr__status-bar" aria-live="polite">
        <span className="scan-qr__phase">Status: {phase.replace('-', ' ')}</span>
        {!window.isSecureContext && (
          <span className="scan-qr__hint">
            Live camera needs HTTPS (or localhost). Paste/upload still works on HTTP.
          </span>
        )}
      </div>

      <div id={readerId} className="scan-qr__viewport" />

      {phase === 'idle' && (
        <button type="button" className="btn btn--primary scan-qr__start" onClick={() => void startCamera()}>
          Start camera
        </button>
      )}

      {(phase === 'scanning' || phase === 'camera-starting' || phase === 'loading-module') && (
        <button type="button" className="btn btn--ghost scan-qr__start" onClick={() => void stopCamera()}>
          Stop camera
        </button>
      )}

      {error && <p className="select-machine__status select-machine__status--error">{error}</p>}
      {phase === 'resolving' && <p className="select-machine__status">Opening machine…</p>}
      {phase === 'success' && openedAsPopup && (
        <p className="select-machine__status">
          Machine selected. If this tab did not close automatically, switch back to the main tab.
        </p>
      )}

      <form className="scan-qr__form" onSubmit={(event) => void handlePaste(event)}>
        <label htmlFor="qr-paste">Paste QR URL or serial</label>
        <input
          id="qr-paste"
          type="text"
          value={paste}
          onChange={(event) => setPaste(event.target.value)}
          placeholder="https://…/m/17478 or A3279"
        />
        <button type="submit" className="btn btn--primary" disabled={phase === 'resolving' || !paste.trim()}>
          Open machine
        </button>
      </form>

      <label className="scan-qr__file">
        Upload QR image
        <input
          type="file"
          accept="image/*"
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
      </label>

      <details className="scan-qr__debug">
        <summary>Diagnostic log ({debugLog.length})</summary>
        <div className="scan-qr__debug-actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              clearScanDebugLog()
              refreshDebugLog()
            }}
          >
            Clear log
          </button>
        </div>
        <pre>{debugLog.length > 0 ? debugLog.join('\n') : 'No events yet.'}</pre>
      </details>
    </div>
  )
}
