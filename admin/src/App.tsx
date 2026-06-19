import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { Shield, DropletIcon, Map, BarChart3, AlertTriangle, Settings, Activity, CheckSquare } from 'lucide-react'

// ── Placeholder page component ────────────────────────────────────────────────
function PlaceholderPage({ title, description, phase }: { title: string; description: string; phase: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-4 text-center p-8">
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-navy-900 to-navy-700 flex items-center justify-center">
        <Shield className="w-10 h-10 text-white" />
      </div>
      <div>
        <h1 className="text-2xl font-bold text-text-primary mb-2">{title}</h1>
        <p className="text-text-muted mb-1">{description}</p>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-600/10 text-blue-600 border border-blue-600/20">
          Implemented in {phase}
        </span>
      </div>
    </div>
  )
}

// ── Sidebar nav items ─────────────────────────────────────────────────────────
const navItems = [
  { to: '/dashboard', icon: BarChart3, label: 'Dashboard', phase: 'Phase 10' },
  { to: '/monitoring', icon: Activity, label: 'Risk Monitor', phase: 'Phase 10' },
  { to: '/map', icon: Map, label: 'Error Map', phase: 'Phase 10' },
  { to: '/alerts', icon: AlertTriangle, label: 'Alert Analytics', phase: 'Phase 12' },
  { to: '/validation', icon: CheckSquare, label: 'Validation', phase: 'Phase 11' },
  { to: '/calibration', icon: Settings, label: 'Calibration', phase: 'Phase 11' },
  { to: '/moderation', icon: DropletIcon, label: 'Moderation', phase: 'Phase 11' },
]

// ── Sidebar ────────────────────────────────────────────────────────────────────
function Sidebar() {
  return (
    <aside className="w-64 flex-shrink-0 bg-white border-r border-slate-100 flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-navy-900 to-navy-700 flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="font-bold text-text-primary text-sm leading-tight">FloodGuard</p>
            <p className="text-xs text-text-muted leading-tight">Admin Console</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar-item ${isActive ? 'active' : ''}`
            }
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-slate-100">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-navy-900 flex items-center justify-center text-white text-xs font-semibold">
            FG
          </div>
          <div>
            <p className="text-sm font-medium text-text-primary">Admin</p>
            <p className="text-xs text-text-muted">FloodGuard Solutions</p>
          </div>
        </div>
      </div>
    </aside>
  )
}

// ── Header ─────────────────────────────────────────────────────────────────────
function Header({ title }: { title?: string }) {
  return (
    <header className="h-14 border-b border-slate-100 bg-white flex items-center justify-between px-6 flex-shrink-0">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold text-text-primary">{title ?? 'FloodGuard Admin'}</h2>
        <span className="px-2 py-0.5 rounded-full bg-risk-low/10 text-risk-low text-xs font-medium border border-risk-low/20">
          Hyderabad
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs text-text-muted">
          <span className="w-1.5 h-1.5 rounded-full bg-risk-low inline-block animate-pulse" />
          System Online
        </span>
      </div>
    </header>
  )
}

// ── App layout ────────────────────────────────────────────────────────────────
function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-slate-50 font-sans overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="/dashboard"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Dashboard"
                description="Real-time overview of risk levels, active alerts, and system health."
                phase="Phase 10"
              />
            </AdminLayout>
          }
        />
        <Route
          path="/monitoring"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Risk Monitoring"
                description="Predicted vs observed rainfall, MAE/bias metrics, error map."
                phase="Phase 10"
              />
            </AdminLayout>
          }
        />
        <Route
          path="/map"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Error Map"
                description="Hex-level prediction error choropleth overlay."
                phase="Phase 10"
              />
            </AdminLayout>
          }
        />
        <Route
          path="/alerts"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Alert Analytics"
                description="Sent vs delivered metrics, coverage heatmap."
                phase="Phase 12"
              />
            </AdminLayout>
          }
        />
        <Route
          path="/validation"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Validation"
                description="Confusion matrix, hotspot ranking, reports vs risk overlay."
                phase="Phase 11"
              />
            </AdminLayout>
          }
        />
        <Route
          path="/calibration"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Calibration"
                description="FSI weights, IDF thresholds, bias factors, backtest."
                phase="Phase 11"
              />
            </AdminLayout>
          }
        />
        <Route
          path="/moderation"
          element={
            <AdminLayout>
              <PlaceholderPage
                title="Report Moderation"
                description="Verify, reject, or mark spam on user-submitted flood reports."
                phase="Phase 11"
              />
            </AdminLayout>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
