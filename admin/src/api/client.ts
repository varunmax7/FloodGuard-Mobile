import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'

export const api = axios.create({ baseURL: BASE })

// Attach JWT on every request
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('fg_admin_access')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auto-refresh on 401
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    if (err.response?.status === 401 && !err.config._retry) {
      err.config._retry = true
      const refresh = localStorage.getItem('fg_admin_refresh')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE}/auth/token/refresh/`, { refresh })
          localStorage.setItem('fg_admin_access', data.access)
          err.config.headers.Authorization = `Bearer ${data.access}`
          return api(err.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

export const adminApi = {
  login: (phone: string, password: string) =>
    api.post('/admin/auth/login/', { phone, password }).then((r) => r.data),
  me: () => api.get('/admin/auth/me/').then((r) => r.data),

  // Audit
  auditCalibration: () => api.get('/admin/audit/calibration/').then((r) => r.data),
  auditModeration:  () => api.get('/admin/audit/moderation/').then((r) => r.data),

  // Calibration (§2.3)
  getWeights:    () => api.get('/admin/calibrate/weights/').then((r) => r.data),
  putWeights: (data: object) => api.put('/admin/calibrate/weights/', data).then((r) => r.data),

  // Moderation (§2.5)
  moderationQueue: () => api.get('/admin/moderation/queue/').then((r) => r.data),
  moderationAction: (id: string, action: string) =>
    api.post(`/admin/moderation/${id}/action/`, { action }).then((r) => r.data),

  // §2.3 Calibration Console
  getWeights:         ()                                   => api.get('/admin/calibrate/weights/').then((r) => r.data),
  putWeights:         (data: object)                       => api.put('/admin/calibrate/weights/', data).then((r) => r.data),
  calibratePreview:   (weights: object, date?: string)     => api.post('/admin/calibrate/preview/', { weights, date }).then((r) => r.data),
  calibrateBacktest:  (weights: object)                    => api.post('/admin/calibrate/backtest/', { weights }).then((r) => r.data),

  // §2.4 System Health
  healthFeeds:    () => api.get('/admin/health/feeds/').then((r) => r.data),
  healthStations: () => api.get('/admin/health/stations/').then((r) => r.data),
  healthRadar:    () => api.get('/admin/health/radar/').then((r) => r.data),

  // §2.5 Moderation
  moderationQueue:  ()                           => api.get('/admin/moderation/queue/').then((r) => r.data),
  moderationAction: (id: string, action: string) => api.post(`/admin/moderation/${id}/action/`, { action }).then((r) => r.data),

  // §2.6 Analytics
  analyticsAlerts: () => api.get('/admin/analytics/alerts/').then((r) => r.data),
  analyticsUsage:  () => api.get('/admin/analytics/usage/').then((r) => r.data),

  // §2.1 Forecast Verification
  verifyStations:   ()                             => api.get('/admin/verify/stations/').then((r) => r.data),
  verifyTimeseries: (id: string, window: number)   => api.get(`/admin/verify/stations/${id}/timeseries/?window=${window}`).then((r) => r.data),
  verifyErrors:     (window = 72)                  => api.get(`/admin/verify/errors/?window=${window}`).then((r) => r.data),
  verifyErrorMap:   ()                             => api.get('/admin/verify/error-map/').then((r) => r.data),

  // §2.2 Report-vs-Risk Validation
  validateReportsVsRisk:  (from?: string, to?: string) => api.get('/admin/validate/reports-vs-risk/', { params: { from, to } }).then((r) => r.data),
  validateConfusion:      (from?: string, to?: string) => api.get('/admin/validate/confusion/',        { params: { from, to } }).then((r) => r.data),
  validateHotspotRanking: ()                           => api.get('/admin/validate/hotspot-ranking/').then((r) => r.data),

  // Health (§2.4)
  healthFeeds: () => api.get('/admin/health/feeds/').then((r) => r.data),
}
