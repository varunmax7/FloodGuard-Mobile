import Layout from '../components/Layout'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../api/client'
import { CheckCircle, XCircle, AlertOctagon } from 'lucide-react'

type Action = 'VERIFY' | 'REJECT' | 'SPAM'

export default function ModerationPage() {
  const qc = useQueryClient()

  const { data: queue, isLoading } = useQuery({
    queryKey: ['moderation-queue'],
    queryFn: adminApi.moderationQueue,
    retry: false,
  })
  const { data: log } = useQuery({
    queryKey: ['audit-moderation'],
    queryFn: adminApi.auditModeration,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: Action }) =>
      adminApi.moderationAction(id, action),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['moderation-queue'] })
      qc.invalidateQueries({ queryKey: ['audit-moderation'] })
    },
  })

  const act = (id: string, action: Action) => mutation.mutate({ id, action })

  return (
    <Layout title="Moderation Queue">
      <div className="max-w-4xl mx-auto flex flex-col gap-6">
        {/* Queue */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold text-slate-900">Pending Reports</h3>
            <span className="text-[12px] text-slate-400">
              {Array.isArray(queue) ? `${queue.length} pending` : '—'}
            </span>
          </div>
          {isLoading ? (
            <div className="px-5 py-8 text-center text-[13px] text-slate-400">Loading…</div>
          ) : Array.isArray(queue) && queue.length === 0 ? (
            <div className="px-5 py-8 text-center text-[13px] text-slate-400">
              No pending reports. ✓
            </div>
          ) : (
            <div className="divide-y divide-slate-50">
              {(queue ?? []).map((r: any) => (
                <div key={r.id} className="px-5 py-4 flex items-center justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-medium text-slate-700 truncate">
                      {r.depth} — {r.road}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {r.id?.slice(0, 8)}… · {r.observed_at ? new Date(r.observed_at).toLocaleString() : ''}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => act(r.id, 'VERIFY')}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[12px] font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100">
                      <CheckCircle size={13} /> Verify
                    </button>
                    <button onClick={() => act(r.id, 'REJECT')}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[12px] font-medium bg-red-50 text-red-700 hover:bg-red-100">
                      <XCircle size={13} /> Reject
                    </button>
                    <button onClick={() => act(r.id, 'SPAM')}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[12px] font-medium bg-slate-50 text-slate-600 hover:bg-slate-100">
                      <AlertOctagon size={13} /> Spam
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Moderation audit log */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="text-[14px] font-semibold text-slate-900">Moderation Audit Log</h3>
          </div>
          <div className="divide-y divide-slate-50">
            {Array.isArray(log) && log.length > 0 ? log.map((l: any, i: number) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-[13px]">
                <div>
                  <span className="font-medium text-slate-700">{l.action}</span>
                  <span className="text-slate-400 ml-2">by {l.actor}</span>
                  {l.report_id && <span className="text-slate-300 ml-2">report {l.report_id?.slice(0,8)}…</span>}
                </div>
                <span className="text-[11px] text-slate-400">{new Date(l.ts).toLocaleString()}</span>
              </div>
            )) : (
              <div className="px-5 py-6 text-center text-[13px] text-slate-400">No actions recorded yet.</div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
