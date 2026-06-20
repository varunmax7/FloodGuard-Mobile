import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { adminApi } from '../api/client'

export type Role = 'ADMIN' | 'OPERATOR' | 'VIEWER'

interface AuthUser { id: string; phone: string; role: Role }
interface AuthCtx {
  user: AuthUser | null
  loading: boolean
  login: (phone: string, password: string) => Promise<void>
  logout: () => void
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('fg_admin_access')
    if (!token) { setLoading(false); return }
    adminApi.me()
      .then(setUser)
      .catch(() => localStorage.clear())
      .finally(() => setLoading(false))
  }, [])

  async function login(phone: string, password: string) {
    const data = await adminApi.login(phone, password)
    localStorage.setItem('fg_admin_access',  data.access)
    localStorage.setItem('fg_admin_refresh', data.refresh)
    setUser(data.user)
  }

  function logout() {
    localStorage.removeItem('fg_admin_access')
    localStorage.removeItem('fg_admin_refresh')
    setUser(null)
  }

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>
}

export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}

/** True if the user's role satisfies the required minimum level. */
export function hasRole(userRole: Role, required: Role): boolean {
  const rank: Record<Role, number> = { ADMIN: 3, OPERATOR: 2, VIEWER: 1 }
  return rank[userRole] >= rank[required]
}
