import Layout from '../components/Layout'
import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../api/client'
import { api } from '../api/client'
import { Activity, AlertTriangle, BarChart3, Users } from 'lucide-react'

function StatCard({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: string; color: string
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5 flex items-center gap-4 shadow-sm">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <div className="text-2xl font-bold text-slate-900">{value}</div>
        <div className="text-[12px] text-slate-500 mt-0.5">{label}</div>
      </div>
    </div>
  )
}

export default function OverviewPage() {
  const { data: feeds } = useQuery({
    queryKey: ['health-feeds'],
    queryFn: adminApi.healthFeeds,
    retry: false,
  })
  const { data: overview } = useQuery({
    queryKey: ['risk-overview'],
    queryFn: () => api.get('/risk/overview/').then((r) => r.data),
    retry: false,
  })

  return (
    <Layout title="Overview">
      <div className="max-w-5xl mx-auto flex flex-col gap-6">
        {/* Stat cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={AlertTriangle} label="High/Severe Hexes"
            value={overview ? `${Math.round((overview.summary?.high + overview.summary?.severe) * (overview.total_hexes ?? 0) / 100)}` : '—'}
            color="bg-orange-500" />
          <StatCard icon={BarChart3} label="Total Hex Cells"
            value={overview?.total_hexes?.toLocaleString() ?? '—'}
            color="bg-blue-600" />
          <StatCard icon={Activity} label="Model Confidence"
            value={overview ? `${overview.confidence}%` : '—'}
            color="bg-emerald-500" />
          <StatCard icon={Users} label="Data Feeds"
            value={Array.isArray(feeds) ? `${feeds.length}` : '—'}
            color="bg-violet-500" />
        </div>

        {/* Feed health */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="text-[14px] font-semibold text-slate-900">Data Feed Status</h3>
          </div>
          <div className="divide-y divide-slate-50">
            {Array.isArray(feeds) && feeds.length > 0 ? feeds.map((f: any, i: number) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-[13px]">
                <span className="font-medium text-slate-700">{f.source}</span>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${f.ok ? 'bg-emerald-500' : 'bg-red-400'}`} />
                  <span className="text-slate-400">{f.last_ts ? new Date(f.last_ts).toLocaleTimeString() : 'No data'}</span>
                </div>
              </div>
            )) : (
              <div className="px-5 py-8 text-center text-slate-400 text-[13px]">
                No feed data available — start the Celery worker and ingest pipeline.
              </div>
            )}
          </div>
        </div>

        {/* Risk distribution */}
        {overview?.summary && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-[14px] font-semibold text-slate-900 mb-4">Risk Distribution</h3>
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'Severe', pct: overview.summary.severe, color: '#EF4444' },
                { label: 'High',   pct: overview.summary.high,   color: '#F97316' },
                { label: 'Moderate', pct: overview.summary.moderate, color: '#FACC15' },
                { label: 'Low',    pct: overview.summary.low,    color: '#22C55E' },
              ].map((r) => (
                <div key={r.label} className="text-center">
                  <div className="text-2xl font-bold" style={{ color: r.color }}>
                    {r.pct.toFixed(1)}%
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">{r.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
