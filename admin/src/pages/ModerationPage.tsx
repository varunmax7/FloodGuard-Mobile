import { useState } from 'react'
import Layout from '../components/Layout'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../api/client'
import { CheckCircle, XCircle, AlertOctagon, MapPin, Clock, Droplets, Car, Copy, X, Image as ImageIcon, AlertTriangle } from 'lucide-react'

type Action = 'VERIFY' | 'REJECT' | 'SPAM'

interface Report {
  id: string
  depth: string
  road: string
  status: string
  photo_url: string
  observed_at: string
  created_at: string
  lat: number
  lon: number
  hex: string | null
  ward: string | null
  duplicate_hint: boolean
  duplicate_count: number
}

const depthLabels: Record<string, string> = {
  ANKLE: 'Ankle deep',
  KNEE: 'Knee deep',
  WAIST: 'Waist deep',
  VEHICLE: 'Vehicle level',
}

const roadLabels: Record<string, { label: string; color: string }> = {
  PASSABLE: { label: 'Passable', color: '#22c55e' },
  DIFFICULT: { label: 'Difficult', color: '#f97316' },
  BLOCKED: { label: 'Blocked', color: '#ef4444' },
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function ModerationPage() {
  const qc = useQueryClient()
  const [photoModal, setPhotoModal] = useState<string | null>(null)

  const { data: queue, isLoading } = useQuery({
    queryKey: ['moderation-queue'],
    queryFn: adminApi.moderationQueue,
    refetchInterval: 10000, // poll every 10s
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
      <div className="max-w-5xl mx-auto flex flex-col gap-6">
        {/* Pending Reports Queue */}
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
              {(queue ?? []).map((r: Report) => (
                <div key={r.id} className="px-5 py-4">
                  <div className="flex gap-4">
                    {/* Photo */}
                    <div className="flex-shrink-0">
                      {r.photo_url ? (
                        <button
                          onClick={() => setPhotoModal(r.photo_url)}
                          className="block w-[120px] h-[90px] rounded-lg overflow-hidden border border-slate-200 hover:border-blue-400 transition-colors cursor-pointer relative group"
                        >
                          <img
                            src={r.photo_url}
                            alt="Flood report"
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              (e.target as HTMLImageElement).style.display = 'none'
                              ;(e.target as HTMLImageElement).parentElement!.classList.add('bg-slate-100')
                            }}
                          />
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                            <ImageIcon size={18} className="text-white opacity-0 group-hover:opacity-80 transition-opacity drop-shadow" />
                          </div>
                        </button>
                      ) : (
                        <div className="w-[120px] h-[90px] rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center">
                          <ImageIcon size={24} className="text-slate-300" />
                        </div>
                      )}
                    </div>

                    {/* Details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[13px] font-semibold text-slate-800">
                          <Droplets size={13} className="inline mr-1 text-blue-500" />
                          {depthLabels[r.depth] || r.depth}
                        </span>
                        <span className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                          style={{
                            backgroundColor: (roadLabels[r.road]?.color || '#94a3b8') + '18',
                            color: roadLabels[r.road]?.color || '#94a3b8',
                          }}>
                          <Car size={11} className="inline mr-0.5" />
                          {roadLabels[r.road]?.label || r.road}
                        </span>
                        {r.duplicate_hint && (
                          <span className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-amber-50 text-amber-700">
                            <AlertTriangle size={11} className="inline mr-0.5" />
                            {r.duplicate_count} similar
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-3 text-[11px] text-slate-400 mb-2">
                        <span>
                          <MapPin size={11} className="inline mr-0.5" />
                          {r.lat?.toFixed(4)}, {r.lon?.toFixed(4)}
                          {r.ward && <span className="ml-1 text-slate-500">({r.ward})</span>}
                        </span>
                        <span>
                          <Clock size={11} className="inline mr-0.5" />
                          {timeAgo(r.observed_at)}
                          <span className="ml-1 text-slate-300">
                            ({new Date(r.observed_at).toLocaleString()})
                          </span>
                        </span>
                      </div>

                      <div className="text-[10px] text-slate-300 flex items-center gap-1">
                        <Copy size={10} />
                        {r.id}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex-shrink-0 flex flex-col gap-1.5 justify-center">
                      <button
                        onClick={() => act(r.id, 'VERIFY')}
                        disabled={mutation.isPending}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
                      >
                        <CheckCircle size={14} /> Verify
                      </button>
                      <button
                        onClick={() => act(r.id, 'REJECT')}
                        disabled={mutation.isPending}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50 transition-colors"
                      >
                        <XCircle size={14} /> Reject
                      </button>
                      <button
                        onClick={() => act(r.id, 'SPAM')}
                        disabled={mutation.isPending}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] font-semibold bg-slate-50 text-slate-600 hover:bg-slate-100 disabled:opacity-50 transition-colors"
                      >
                        <AlertOctagon size={14} /> Spam
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Moderation Audit Log */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="text-[14px] font-semibold text-slate-900">Moderation Audit Log</h3>
          </div>
          <div className="divide-y divide-slate-50">
            {Array.isArray(log) && log.length > 0 ? log.map((l: any, i: number) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-[13px]">
                <div className="flex items-center gap-3">
                  {/* Audit Photo Thumbnail */}
                  <div className="flex-shrink-0">
                    {l.photo_url ? (
                      <button
                        onClick={() => setPhotoModal(l.photo_url)}
                        className="block w-[40px] h-[40px] rounded border border-slate-200 overflow-hidden hover:border-blue-400 transition-colors"
                      >
                        <img src={l.photo_url} alt="Report" className="w-full h-full object-cover" />
                      </button>
                    ) : (
                      <div className="w-[40px] h-[40px] rounded bg-slate-50 border border-slate-100 flex items-center justify-center">
                        <ImageIcon size={14} className="text-slate-300" />
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {l.action === 'VERIFY' && <CheckCircle size={14} className="text-emerald-500" />}
                    {l.action === 'REJECT' && <XCircle size={14} className="text-red-500" />}
                    {l.action === 'SPAM' && <AlertOctagon size={14} className="text-slate-400" />}
                    <span className="font-medium text-slate-700">{l.action}</span>
                    <span className="text-slate-400">by {l.actor}</span>
                    {l.report_id && (
                      <span className="text-slate-300">report {l.report_id?.slice(0, 8)}…</span>
                    )}
                  </div>
                </div>
                <span className="text-[11px] text-slate-400">
                  {new Date(l.ts).toLocaleString()}
                </span>
              </div>
            )) : (
              <div className="px-5 py-6 text-center text-[13px] text-slate-400">
                No actions recorded yet.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Photo Modal */}
      {photoModal && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
          onClick={() => setPhotoModal(null)}
        >
          <div className="relative max-w-3xl max-h-[85vh]" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setPhotoModal(null)}
              className="absolute -top-3 -right-3 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center hover:bg-slate-100 z-10"
            >
              <X size={16} />
            </button>
            <img
              src={photoModal}
              alt="Full size flood report"
              className="max-w-full max-h-[85vh] rounded-xl shadow-2xl object-contain"
            />
          </div>
        </div>
      )}
    </Layout>
  )
}
