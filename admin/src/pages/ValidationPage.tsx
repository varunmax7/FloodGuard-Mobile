import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import Layout from '../components/Layout'
import { adminApi } from '../api/client'

const LEVELS = ['LOW', 'MODERATE', 'HIGH', 'SEVERE'] as const
type Level = typeof LEVELS[number]

const LEVEL_COLOR: Record<Level, string> = {
  LOW:      'bg-green-100 text-green-700',
  MODERATE: 'bg-yellow-100 text-yellow-700',
  HIGH:     'bg-orange-100 text-orange-700',
  SEVERE:   'bg-red-100 text-red-700',
}

const STATUS_COLOR: Record<string, string> = {
  VERIFIED: 'bg-green-100 text-green-700',
  REJECTED: 'bg-slate-100 text-slate-500',
}

function fmt(v: number) { return (v * 100).toFixed(0) + '%' }

type SortKey = 'accuracy' | 'agree' | 'disagree' | 'total'

export default function ValidationPage() {
  const [sortBy, setSortBy] = useState<SortKey>('accuracy')

  const { data: confusion, isLoading: cLoading } = useQuery({
    queryKey: ['validate-confusion'],
    queryFn:  adminApi.validateConfusion,
  })

  const { data: reports = [], isLoading: rLoading } = useQuery({
    queryKey: ['validate-reports'],
    queryFn:  adminApi.validateReportsVsRisk,
  })

  const { data: hotspots = [], isLoading: hLoading } = useQuery({
    queryKey: ['validate-hotspots'],
    queryFn:  adminApi.validateHotspotRanking,
  })

  const matrix = confusion?.matrix ?? {}
  const sorted = [...hotspots].sort((a: any, b: any) => b[sortBy] - a[sortBy])

  return (
    <Layout title="Validation">

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total events',     value: confusion?.total           ?? '—' },
          { label: 'False negatives',  value: confusion?.false_negatives ?? '—', warn: true },
          { label: 'False positives',  value: confusion?.false_positives ?? '—', warn: true },
          { label: 'Areas ranked',     value: hotspots.length                   },
        ].map(({ label, value, warn }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-100 shadow-sm px-4 py-3">
            <div className="text-[11px] text-slate-400 font-medium">{label}</div>
            <div className={`text-[26px] font-bold mt-0.5 ${warn && value > 0 ? 'text-red-500' : 'text-slate-900'}`}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Confusion matrix + hotspot ranking ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">

        {/* Confusion matrix */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-[13px] font-semibold text-slate-700">Confusion Matrix — Predicted × Actual</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Actual: VERIFIED = flooded, REJECTED = not flooded</p>
          </div>
          {cLoading ? (
            <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
          ) : (
            <div className="p-4">
              <table className="w-full text-[12px] border-collapse">
                <thead>
                  <tr>
                    <th className="text-left pb-2 text-slate-500 font-medium">Predicted ↓</th>
                    <th className="text-center pb-2 text-emerald-600 font-semibold">Flooded</th>
                    <th className="text-center pb-2 text-slate-500 font-semibold">Not Flooded</th>
                    <th className="text-center pb-2 text-slate-400 font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {LEVELS.map(lvl => {
                    const row = matrix[lvl] ?? { flooded: 0, not_flooded: 0 }
                    const total = row.flooded + row.not_flooded
                    const isMiss = (lvl === 'HIGH' || lvl === 'SEVERE') && row.not_flooded > 0
                    const isFP   = (lvl === 'LOW'  || lvl === 'MODERATE') && row.flooded > 0
                    return (
                      <tr key={lvl} className="hover:bg-slate-50">
                        <td className="py-2 pr-3">
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${LEVEL_COLOR[lvl]}`}>{lvl}</span>
                        </td>
                        <td className="text-center py-2 font-mono font-semibold text-emerald-700">{row.flooded}</td>
                        <td className={`text-center py-2 font-mono font-semibold ${isMiss ? 'text-red-600 bg-red-50' : isFP ? 'bg-amber-50 text-amber-700' : 'text-slate-500'}`}>
                          {row.not_flooded}
                        </td>
                        <td className="text-center py-2 text-slate-400">{total}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <div className="mt-3 flex gap-4 text-[11px] text-slate-400">
                <span><span className="text-red-500 font-semibold">Red</span> = missed flood (false negative)</span>
                <span><span className="text-amber-600 font-semibold">Amber</span> = false alarm</span>
              </div>
            </div>
          )}
        </div>

        {/* Hotspot ranking */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-slate-700">Hotspot Accuracy Ranking</h3>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as SortKey)}
              className="text-[11px] border border-slate-200 rounded px-2 py-1 bg-white focus:outline-none"
            >
              <option value="accuracy">Sort: Accuracy</option>
              <option value="disagree">Sort: Disagreements</option>
              <option value="total">Sort: Total events</option>
            </select>
          </div>
          {hLoading ? (
            <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
          ) : sorted.length === 0 ? (
            <div className="p-6 text-center text-sm text-slate-400">No hotspot data yet. Seed fixtures first.</div>
          ) : (
            <div className="overflow-y-auto max-h-[320px]">
              <table className="w-full text-[12px]">
                <thead className="bg-slate-50 sticky top-0">
                  <tr>
                    {['Ward', 'Acc.', '✓', '✗', 'n'].map(h => (
                      <th key={h} className="text-left px-3 py-2 font-medium text-slate-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {sorted.map((r: any) => (
                    <tr key={r.h3_index} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-medium text-slate-800 truncate max-w-[110px]">{r.ward_name || r.h3_index.slice(0,8)}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          <div className="w-14 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                            <div className="h-full bg-blue-500 rounded-full" style={{ width: fmt(r.accuracy) }} />
                          </div>
                          <span className="text-slate-600">{fmt(r.accuracy)}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2 text-emerald-600 font-semibold">{r.agree}</td>
                      <td className="px-3 py-2 text-red-500 font-semibold">{r.disagree}</td>
                      <td className="px-3 py-2 text-slate-400">{r.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>

      {/* ── Per-event timeline ── */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100">
          <h3 className="text-[13px] font-semibold text-slate-700">Per-Event Timeline</h3>
          <p className="text-[11px] text-slate-400 mt-0.5">Reports with risk level active at report time (last 30 days, max 200)</p>
        </div>
        {rLoading ? (
          <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
        ) : reports.length === 0 ? (
          <div className="p-6 text-center text-sm text-slate-400">No verified/rejected reports in range.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead className="bg-slate-50">
                <tr>
                  {['Time', 'Status', 'Depth', 'Risk at time', 'Hex'].map(h => (
                    <th key={h} className="text-left px-3 py-2 font-medium text-slate-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {reports.map((r: any) => (
                  <tr key={r.report_id} className="hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-500 whitespace-nowrap">
                      {new Date(r.observed_at).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${STATUS_COLOR[r.status] ?? ''}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600">{r.depth}</td>
                    <td className="px-3 py-2">
                      {r.risk_at_time
                        ? <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${LEVEL_COLOR[r.risk_at_time as Level] ?? ''}`}>{r.risk_at_time}</span>
                        : <span className="text-slate-300">—</span>}
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-400">{r.hex?.slice(0, 10)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </Layout>
  )
}
