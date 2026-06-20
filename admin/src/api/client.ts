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

  // Health (§2.4)
  healthFeeds: () => api.get('/admin/health/feeds/').then((r) => r.data),
}
