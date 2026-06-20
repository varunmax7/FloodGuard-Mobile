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
import ForecastVerificationPage from './pages/ForecastVerificationPage'
import ValidationPage from './pages/ValidationPage'
import HealthPage from './pages/HealthPage'
import AnalyticsPage from './pages/AnalyticsPage'
import ExportPage from './pages/ExportPage'

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
              <RequireAuth><ForecastVerificationPage /></RequireAuth>
            } />
            <Route path="/validation" element={
              <RequireAuth><ValidationPage /></RequireAuth>
            } />
            <Route path="/health"    element={<RequireAuth><HealthPage /></RequireAuth>} />
            <Route path="/analytics" element={<RequireAuth><AnalyticsPage /></RequireAuth>} />
            <Route path="/export"    element={<RequireAuth><ExportPage /></RequireAuth>} />

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
