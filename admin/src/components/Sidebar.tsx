import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, TrendingUp, ClipboardCheck, Sliders,
  Activity, Shield, BarChart3, Download, ScrollText, ShieldAlert, LogOut,
} from 'lucide-react'
import { useAuth, hasRole } from '../auth/AuthContext'

const NAV = [
  { to: '/',            icon: LayoutDashboard, label: 'Overview',             minRole: 'VIEWER'   as const },
  { to: '/verify',      icon: TrendingUp,      label: 'Forecast Verification', minRole: 'VIEWER'   as const },
  { to: '/validation',  icon: ClipboardCheck,  label: 'Validation',            minRole: 'VIEWER'   as const },
  { to: '/calibration', icon: Sliders,         label: 'Calibration',           minRole: 'OPERATOR' as const },
  { to: '/health',      icon: Activity,        label: 'System Health',         minRole: 'VIEWER'   as const },
  { to: '/moderation',  icon: Shield,          label: 'Moderation',            minRole: 'OPERATOR' as const },
  { to: '/analytics',   icon: BarChart3,       label: 'Analytics',             minRole: 'VIEWER'   as const },
  { to: '/export',      icon: Download,        label: 'Export',                minRole: 'VIEWER'   as const },
  { to: '/audit',       icon: ScrollText,      label: 'Audit Log',             minRole: 'VIEWER'   as const },
]

export default function Sidebar() {
  const { user, logout } = useAuth()

  const roleBadge: Record<string, string> = {
    ADMIN:    'bg-blue-100 text-blue-700',
    OPERATOR: 'bg-amber-100 text-amber-700',
    VIEWER:   'bg-slate-100 text-slate-600',
  }

  return (
    <aside className="w-60 flex-shrink-0 bg-white border-r border-slate-100 flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-100 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl overflow-hidden flex-shrink-0 bg-white ring-1 ring-slate-200">
          <img src="/logo.png" alt="FloodGuard" className="w-full h-full object-contain" />
        </div>
        <div>
          <div className="text-[13px] font-bold text-slate-900 leading-tight">FloodGuard</div>
          <div className="text-[11px] text-slate-400 leading-tight">Admin Console</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-3 flex flex-col gap-0.5 overflow-y-auto">
        {NAV.map(({ to, icon: Icon, label, minRole }) => {
          const allowed = user ? hasRole(user.role, minRole) : false
          if (!allowed) return null
          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'
                }`
              }
            >
              <Icon size={15} />
              <span>{label}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
            {user?.phone?.slice(-2) ?? 'FG'}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-medium text-slate-900 truncate">{user?.phone}</div>
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${roleBadge[user?.role ?? 'VIEWER']}`}>
              {user?.role}
            </span>
          </div>
          <button onClick={logout} className="text-slate-400 hover:text-slate-700 transition-colors">
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  )
}
