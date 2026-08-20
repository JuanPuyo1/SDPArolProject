import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useActiveMachine } from '../src/hooks/useActiveMachine'
import ProtectedRoute from './ProtectedRoute'

export default function RequireMachineRoute({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <MachineFocusGate>{children}</MachineFocusGate>
    </ProtectedRoute>
  )
}

export function MachineFocusGate({ children }: { children: ReactNode }) {
  const { focus, ready } = useActiveMachine()
  const location = useLocation()

  if (!ready) {
    return (
      <div className="page-loading">
        <p>Checking session…</p>
      </div>
    )
  }

  if (!focus) {
    return (
      <Navigate
        to="/select"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    )
  }

  return children
}
