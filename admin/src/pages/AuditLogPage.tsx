import { useQuery } from '@tanstack/react-query'
import { adminApi } from '../api/client'
import Layout from '../components/Layout'

function ts(val: string) {
  return new Date(val).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

export default function AuditLogPage() {
  const { data: calibLogs, isLoading: cLoading } = useQuery({
    queryKey: ['audit-calibration'],
    queryFn: adminApi.auditCalibration,
  })

  const { data: modLogs, isLoading: mLoading } = useQuery({
    queryKey: ['audit-moderation'],
    queryFn: adminApi.auditModeration,
  })

  return (
    <Layout title="Audit Log">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Calibration audit */}
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Calibration changes</h2>
          <div className="rounded-xl border border-slate-100 overflow-hidden">
            {cLoading ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
            ) : !calibLogs?.length ? (
              <div className="p-6 text-center text-sm text-slate-400">No calibration changes yet.</div>
            ) : (
              <table className="w-full text-[13px]">
                <thead className="bg-slate-50 border-b border-slate-100">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Actor</th>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Type</th>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {calibLogs.map((l: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-mono text-slate-700">{l.actor}</td>
                      <td className="px-4 py-2.5">
                        <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[11px] font-semibold">
                          {l.change_type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-slate-400">{ts(l.ts)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Moderation audit */}
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">Moderation actions</h2>
          <div className="rounded-xl border border-slate-100 overflow-hidden">
            {mLoading ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
            ) : !modLogs?.length ? (
              <div className="p-6 text-center text-sm text-slate-400">No moderation actions yet.</div>
            ) : (
              <table className="w-full text-[13px]">
                <thead className="bg-slate-50 border-b border-slate-100">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Actor</th>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Action</th>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Report</th>
                    <th className="text-left px-4 py-2.5 font-medium text-slate-500">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {modLogs.map((l: any, i: number) => {
                    const badge: Record<string, string> = {
                      VERIFY: 'bg-emerald-50 text-emerald-700',
                      REJECT: 'bg-red-50 text-red-700',
                      SPAM:   'bg-amber-50 text-amber-700',
                    }
                    return (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-2.5 font-mono text-slate-700">{l.actor ?? '—'}</td>
                        <td className="px-4 py-2.5">
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${badge[l.action] ?? 'bg-slate-100 text-slate-600'}`}>
                            {l.action}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 font-mono text-[11px] text-slate-400 truncate max-w-[100px]">
                          {l.report_id ? l.report_id.slice(0, 8) + '…' : '—'}
                        </td>
                        <td className="px-4 py-2.5 text-slate-400">{ts(l.ts)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

      </div>
    </Layout>
  )
}
