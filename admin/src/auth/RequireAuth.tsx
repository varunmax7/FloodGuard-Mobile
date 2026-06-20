import { Navigate, useLocation } from 'react-router-dom'
import { useAuth, hasRole, Role } from './AuthContext'

interface Props {
  children: React.ReactNode
  role?: Role  // minimum required role (default: VIEWER)
}

export default function RequireAuth({ children, role = 'VIEWER' }: Props) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-400 text-sm">
        Loading…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!hasRole(user.role, role)) {
    return (
      <div className="flex h-screen items-center justify-center flex-col gap-3 text-slate-500">
        <span className="text-4xl">🔒</span>
        <p className="font-medium">Access denied — requires {role} role.</p>
        <p className="text-sm">Your role: <strong>{user.role}</strong></p>
      </div>
    )
  }

  return <>{children}</>
}
