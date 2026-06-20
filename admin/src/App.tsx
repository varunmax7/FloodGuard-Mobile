import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'

// ── SVG icon components (no icon lib dependency) ──────────────────────────────
const Icon = ({ d, size = 16 }: { d: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
)
const icons = {
  shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
  chart: 'M18 20V10M12 20V4M6 20v-6',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  map: 'M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3V6z',
  bell: 'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0',
  check: 'M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
  drop: 'M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z',
}

// ── Placeholder page ───────────────────────────────────────────────────────────
function PlaceholderPage({ title, description, phase }: { title: string; description: string; phase: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-4 text-center p-8">
      <div className="w-20 h-20 rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #0B2545, #13315C)' }}>
        <Icon d={icons.shield} size={40} />
      </div>
      <div>
        <h1 className="text-2xl font-bold mb-2" style={{ color: '#0F172A' }}>{title}</h1>
        <p className="mb-3" style={{ color: '#64748B' }}>{description}</p>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold" style={{ background: 'rgba(37,99,235,0.1)', color: '#2563EB', border: '1px solid rgba(37,99,235,0.2)' }}>
          {phase}
        </span>
      </div>
    </div>
  )
}

// ── Sidebar nav ────────────────────────────────────────────────────────────────
const navItems = [
  { to: '/dashboard',   iconKey: 'chart' as const,    label: 'Dashboard',     phase: 'Phase 10' },
  { to: '/monitoring',  iconKey: 'activity' as const,  label: 'Risk Monitor',  phase: 'Phase 10' },
  { to: '/map',         iconKey: 'map' as const,        label: 'Error Map',     phase: 'Phase 10' },
  { to: '/alerts',      iconKey: 'bell' as const,       label: 'Alert Analytics', phase: 'Phase 12' },
  { to: '/validation',  iconKey: 'check' as const,      label: 'Validation',    phase: 'Phase 11' },
  { to: '/calibration', iconKey: 'settings' as const,   label: 'Calibration',   phase: 'Phase 11' },
  { to: '/moderation',  iconKey: 'drop' as const,       label: 'Moderation',    phase: 'Phase 11' },
]

function Sidebar() {
  return (
    <aside style={{ width: 240, flexShrink: 0, background: '#fff', borderRight: '1px solid #F1F5F9', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Logo */}
      <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg,#0B2545,#13315C)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
            <Icon d={icons.shield} size={18} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#0F172A', lineHeight: 1.3 }}>FloodGuard</div>
            <div style={{ fontSize: 11, color: '#64748B', lineHeight: 1.3 }}>Admin Console</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '12px 12px', display: 'flex', flexDirection: 'column', gap: 2, overflowY: 'auto' }}>
        {navItems.map(({ to, iconKey, label }) => (
          <NavLink key={to} to={to} style={({ isActive }) => ({
            display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
            borderRadius: 8, fontSize: 13, fontWeight: 500, textDecoration: 'none',
            transition: 'all 0.15s',
            color: isActive ? '#2563EB' : '#64748B',
            background: isActive ? 'rgba(37,99,235,0.08)' : 'transparent',
          })}>
            <Icon d={icons[iconKey]} size={15} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid #F1F5F9', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#0B2545', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 11, fontWeight: 600 }}>FG</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, color: '#0F172A' }}>Admin</div>
          <div style={{ fontSize: 11, color: '#64748B' }}>FloodGuard Solutions</div>
        </div>
      </div>
    </aside>
  )
}

// ── Header ─────────────────────────────────────────────────────────────────────
function Header() {
  return (
    <header style={{ height: 56, borderBottom: '1px solid #F1F5F9', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px', flexShrink: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: '#0F172A' }}>FloodGuard Admin</span>
        <span style={{ padding: '2px 8px', borderRadius: 20, background: 'rgba(34,197,94,0.1)', color: '#22C55E', fontSize: 11, fontWeight: 600, border: '1px solid rgba(34,197,94,0.2)' }}>Hyderabad</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748B' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22C55E', display: 'inline-block', animation: 'pulse 2s infinite' }} />
        System Online · p0
      </div>
    </header>
  )
}

// ── Layout ─────────────────────────────────────────────────────────────────────
function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', height: '100vh', background: '#F8FAFC', fontFamily: "'Inter', system-ui, sans-serif", overflow: 'hidden' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, overflow: 'hidden' }}>
        <Header />
        <main style={{ flex: 1, overflowY: 'auto', padding: 24 }}>{children}</main>
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
        {navItems.map(({ to, label, phase }) => (
          <Route key={to} path={to} element={
            <AdminLayout>
              <PlaceholderPage title={label} description={`Full implementation in ${phase}.`} phase={phase} />
            </AdminLayout>
          } />
        ))}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
