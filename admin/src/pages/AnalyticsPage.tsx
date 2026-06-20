import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from '../components/ChartWrapper'
import { COLORS } from '../components/ChartWrapper'
import Layout from '../components/Layout'
import { adminApi } from '../api/client'

const LEVEL_COLOR: Record<string, string> = {
  LOW:      COLORS.low,
  MODERATE: COLORS.moderate,
  HIGH:     COLORS.high,
  SEVERE:   COLORS.severe,
}

const STATUS_COLOR: Record<string, string> = {
  DELIVERED: COLORS.low,
  SENT:      COLORS.blue,
  QUEUED:    COLORS.moderate,
  FAILED:    COLORS.severe,
}

export default function AnalyticsPage() {
  const { data: alerts, isLoading: aLoading } = useQuery({
    queryKey: ['analytics-alerts'],
    queryFn:  adminApi.analyticsAlerts,
  })
  const { data: usage, isLoading: uLoading } = useQuery({
    queryKey: ['analytics-usage'],
    queryFn:  adminApi.analyticsUsage,
  })

  const byLevel  = Object.entries(alerts?.by_level  ?? {}).map(([k, v]) => ({ name: k, count: v as number }))
  const byStatus = Object.entries(alerts?.by_status ?? {}).map(([k, v]) => ({ name: k, count: v as number }))

  return (
    <Layout title="Analytics">

      {/* Usage stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Active Users',   value: uLoading ? '…' : usage?.active_users  ?? 0 },
          { label: 'Total Users',    value: uLoading ? '…' : usage?.total_users   ?? 0 },
          { label: 'Reports (30d)',  value: uLoading ? '…' : usage?.reports_30d   ?? 0 },
          { label: 'Dark Hexes',     value: uLoading ? '…' : usage?.dark_hexes    ?? 0, warn: true },
        ].map(({ label, value, warn }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-100 shadow-sm px-4 py-3">
            <div className="text-[11px] text-slate-400 font-medium">{label}</div>
            <div className={`text-[26px] font-bold mt-0.5 ${warn && Number(value) > 0 ? 'text-amber-500' : 'text-slate-900'}`}>{value}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">

        {/* Alerts by level */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
          <h3 className="text-[13px] font-semibold text-slate-700 mb-4">Alerts by Risk Level (30d)</h3>
          {aLoading ? <div className="h-40 flex items-center justify-center text-slate-400 text-sm">Loading…</div> : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={byLevel}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4,4,0,0]}>
                  {byLevel.map(d => <Cell key={d.name} fill={LEVEL_COLOR[d.name] ?? COLORS.muted} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Delivery status */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
          <h3 className="text-[13px] font-semibold text-slate-700 mb-4">FCM Delivery Status (30d)</h3>
          {aLoading ? <div className="h-40 flex items-center justify-center text-slate-400 text-sm">Loading…</div> : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={byStatus}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4,4,0,0]}>
                  {byStatus.map(d => <Cell key={d.name} fill={STATUS_COLOR[d.name] ?? COLORS.muted} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

      </div>

      {/* Top areas */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-[13px] font-semibold text-slate-700">Top Alert Areas (30d)</h3>
        </div>
        {aLoading ? (
          <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
        ) : !(alerts?.top_areas?.length) ? (
          <div className="p-6 text-center text-sm text-slate-400">No alert data. Run seed_p12 first.</div>
        ) : (
          <table className="w-full text-[12px]">
            <thead className="bg-slate-50">
              <tr>
                {['#','Ward / Hex','Alerts'].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 font-medium text-slate-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {(alerts.top_areas as any[]).map((a: any, i: number) => (
                <tr key={a.hex__h3_index} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 text-slate-400">{i+1}</td>
                  <td className="px-4 py-2.5 font-medium text-slate-800">
                    {a.hex__ward_name || a.hex__h3_index?.slice(0,10)}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${Math.min(100, (a.n / (alerts.top_areas[0]?.n || 1)) * 100)}%` }} />
                      </div>
                      <span className="font-semibold text-slate-700">{a.n}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </Layout>
  )
}
