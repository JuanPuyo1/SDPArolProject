import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../src/hooks/useAuth'
import type { UserVisibility } from '../src/types/auth'
import ProtectedRoute from './ProtectedRoute'

type VisibilityRouteProps = {
  children: ReactNode
  allowed: UserVisibility[]
}

export default function VisibilityRoute({ children, allowed }: VisibilityRouteProps) {
  return (
    <ProtectedRoute>
      <VisibilityGate allowed={allowed}>{children}</VisibilityGate>
    </ProtectedRoute>
  )
}

function VisibilityGate({ children, allowed }: VisibilityRouteProps) {
  const { user } = useAuth()
  const location = useLocation()
  const visibility = user?.visibility

  if (!visibility || !allowed.includes(visibility)) {
    return <Navigate to="/machine" replace state={{ from: location.pathname }} />
  }

  return children
}
