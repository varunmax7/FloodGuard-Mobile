import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import RequireAuth from './auth/RequireAuth'
import LoginPage from './auth/LoginPage'
import OverviewPage from './pages/OverviewPage'
import CalibrationPage from './pages/CalibrationPage'
import ModerationPage from './pages/ModerationPage'
import PlaceholderPage from './pages/PlaceholderPage'
import AuditLogPage from './pages/AuditLogPage'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected — VIEWER+ */}
            <Route path="/" element={
              <RequireAuth><OverviewPage /></RequireAuth>
            } />
            <Route path="/verify" element={
              <RequireAuth>
                <PlaceholderPage title="Forecast Verification" section="§2.1 Forecast Verification"
                  phase="Phase 11" description="Predicted vs observed timeseries, error metrics, bias-correction readout." />
              </RequireAuth>
            } />
            <Route path="/validation" element={
              <RequireAuth>
                <PlaceholderPage title="Validation" section="§2.2 Report-vs-Risk Validation"
                  phase="Phase 11" description="Confusion matrix, per-event timeline, hotspot accuracy ranking." />
              </RequireAuth>
            } />
            <Route path="/health" element={
              <RequireAuth>
                <PlaceholderPage title="System Health" section="§2.4 System & Data Health"
                  phase="Phase 12" description="Feed staleness, AWS station uptime, radar anomalies, API error rates." />
              </RequireAuth>
            } />
            <Route path="/analytics" element={
              <RequireAuth>
                <PlaceholderPage title="Analytics" section="§2.6 Alert Analytics"
                  phase="Phase 12" description="FCM delivery receipts, alert rates by area/level, usage stats." />
              </RequireAuth>
            } />
            <Route path="/export" element={
              <RequireAuth>
                <PlaceholderPage title="Export" section="§2.7 Historical Query & Export"
                  phase="Phase 12" description="Filter past risk + reports by area/date, export CSV or GeoJSON." />
              </RequireAuth>
            } />

            {/* Protected — OPERATOR+ */}
            <Route path="/calibration" element={
              <RequireAuth role="OPERATOR"><CalibrationPage /></RequireAuth>
            } />
            <Route path="/moderation" element={
              <RequireAuth role="OPERATOR"><ModerationPage /></RequireAuth>
            } />

            {/* §2.8 Audit Log — any staff */}
            <Route path="/audit" element={
              <RequireAuth><AuditLogPage /></RequireAuth>
            } />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
