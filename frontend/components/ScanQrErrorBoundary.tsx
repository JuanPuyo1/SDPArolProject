import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { logScanDebug, readScanDebugLog } from '../src/api/scanDebug'
import './SelectMachinePage.css'
import './ScanQrPage.css'

type Props = { children: ReactNode }

type State = {
  error: Error | null
}

export default class ScanQrErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    logScanDebug(`boundary: ${error.message}`)
    if (info.componentStack) {
      logScanDebug(`boundary stack: ${info.componentStack.split('\n')[1]?.trim() ?? 'unknown'}`)
    }
  }

  render() {
    if (this.state.error) {
      const log = readScanDebugLog()
      return (
        <div className="scan-qr">
          <header className="scan-qr__header">
            <div className="select-machine__eyebrow">QR access</div>
            <h1 className="select-machine__title">Scanner could not start</h1>
            <p className="select-machine__lead">
              The camera module failed to load. You can still paste a QR URL or upload a photo
              from the machine list, or try again in a new tab.
            </p>
            <p className="select-machine__status select-machine__status--error">
              {this.state.error.message}
            </p>
            <div className="scan-qr__actions">
              <Link to="/select" className="btn btn--ghost">
                Back to machine list
              </Link>
              <a href="/scan" target="_blank" rel="noopener noreferrer" className="btn btn--primary">
                Open scanner in new tab
              </a>
            </div>
          </header>
          {log.length > 0 && (
            <details className="scan-qr__debug">
              <summary>Diagnostic log ({log.length})</summary>
              <pre>{log.join('\n')}</pre>
            </details>
          )}
        </div>
      )
    }

    return this.props.children
  }
}
