import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { X, MapPin, Users, Clock, ExternalLink } from 'lucide-react'
import { adminApi } from '../api/client'
import Layout from '../components/Layout'

function ts(val: string) {
  return new Date(val).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

interface ModLog {
  actor: string | null
  action: 'VERIFY' | 'REJECT' | 'SPAM'
  ts: string
  report_id: string | null
  photo_url: string | null
  description: string | null
  depth: string | null
  road: string | null
  status: string | null
  party_size: number | null
  observed_at: string | null
  created_at: string | null
  lat: number | null
  lon: number | null
  ward: string | null
}

const DEPTH_LABEL: Record<string, string> = {
  ANKLE: 'Ankle deep',
  KNEE: 'Knee deep',
  WAIST: 'Waist deep',
  VEHICLE: 'Vehicle level',
}
const ROAD_LABEL: Record<string, string> = {
  PASSABLE: 'Road passable',
  DIFFICULT: 'Road difficult',
  BLOCKED: 'Road blocked',
}

export default function AuditLogPage() {
  const [selected, setSelected] = useState<ModLog | null>(null)

  const { data: calibLogs, isLoading: cLoading } = useQuery({
    queryKey: ['audit-calibration'],
    queryFn: adminApi.auditCalibration,
  })

  const { data: modLogs, isLoading: mLoading } = useQuery<ModLog[]>({
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
          <p className="text-xs text-slate-400 mb-2">Click any row to see the full report.</p>
          <div className="rounded-xl border border-slate-100 overflow-hidden">
            {mLoading ? (
              <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
            ) : !modLogs?.length ? (
              <div className="p-6 text-center text-sm text-slate-400">No moderation actions yet.</div>
            ) : (
              <table className="w-full text-[13px]">
                <thead className="bg-slate-50 border-b border-slate-100">
                  <tr>
                    <th className="text-left px-3 py-2.5 font-medium text-slate-500 w-16">Photo</th>
                    <th className="text-left px-3 py-2.5 font-medium text-slate-500">Action</th>
                    <th className="text-left px-3 py-2.5 font-medium text-slate-500">Details</th>
                    <th className="text-left px-3 py-2.5 font-medium text-slate-500">Actor</th>
                    <th className="text-left px-3 py-2.5 font-medium text-slate-500">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {modLogs.map((l, i) => {
                    const badge: Record<string, string> = {
                      VERIFY: 'bg-emerald-50 text-emerald-700',
                      REJECT: 'bg-red-50 text-red-700',
                      SPAM:   'bg-amber-50 text-amber-700',
                    }
                    return (
                      <tr
                        key={i}
                        onClick={() => l.report_id && setSelected(l)}
                        className={`hover:bg-slate-50 ${l.report_id ? 'cursor-pointer' : ''}`}
                      >
                        <td className="px-3 py-2">
                          {l.photo_url ? (
                            <img
                              src={l.photo_url}
                              alt="report thumbnail"
                              className="w-12 h-12 rounded object-cover border border-slate-200"
                              loading="lazy"
                            />
                          ) : (
                            <div className="w-12 h-12 rounded bg-slate-100 flex items-center justify-center text-[10px] text-slate-400">
                              No photo
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${badge[l.action] ?? 'bg-slate-100 text-slate-600'}`}>
                            {l.action}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {l.depth ? (
                            <div className="text-[12px]">
                              <div className="font-medium">{DEPTH_LABEL[l.depth] ?? l.depth}</div>
                              <div className="text-slate-400">{ROAD_LABEL[l.road ?? ''] ?? l.road}</div>
                            </div>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-[11px] text-slate-500">{l.actor ?? '—'}</td>
                        <td className="px-3 py-2 text-slate-400 text-[11px]">{ts(l.ts)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

      </div>

      {selected && <ReportModal log={selected} onClose={() => setSelected(null)} />}
    </Layout>
  )
}

function ReportModal({ log, onClose }: { log: ModLog; onClose: () => void }) {
  const gmapsUrl =
    log.lat != null && log.lon != null
      ? `https://www.google.com/maps?q=${log.lat},${log.lon}`
      : null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Flood report</h3>
            <p className="text-[11px] font-mono text-slate-400">{log.report_id}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-100 text-slate-500"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        {log.photo_url ? (
          <img
            src={log.photo_url}
            alt="flood report"
            className="w-full max-h-96 object-cover"
          />
        ) : (
          <div className="w-full h-40 bg-slate-100 flex items-center justify-center text-sm text-slate-400">
            No photo attached to this report
          </div>
        )}

        <div className="px-5 py-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            <Chip label={DEPTH_LABEL[log.depth ?? ''] ?? log.depth ?? '—'} tone="blue" />
            <Chip label={ROAD_LABEL[log.road ?? ''] ?? log.road ?? '—'} tone="amber" />
            <Chip label={`Status: ${log.status ?? '—'}`} tone={log.status === 'VERIFIED' ? 'emerald' : 'slate'} />
          </div>

          {log.description && (
            <div className="rounded-lg bg-slate-50 border border-slate-100 px-3 py-2 text-[13px] text-slate-700 leading-snug italic">
              &ldquo;{log.description}&rdquo;
            </div>
          )}

          <Row icon={<MapPin size={14} />} label="Location">
            {log.lat != null && log.lon != null
              ? `${log.lat.toFixed(5)}, ${log.lon.toFixed(5)}${log.ward ? ` — ${log.ward}` : ''}`
              : '—'}
            {gmapsUrl && (
              <a
                href={gmapsUrl}
                target="_blank"
                rel="noreferrer"
                className="ml-2 text-blue-600 inline-flex items-center gap-1 text-[12px]"
              >
                Open in Maps <ExternalLink size={12} />
              </a>
            )}
          </Row>
          <Row icon={<Users size={14} />} label="Party size">
            {log.party_size ?? 1} {(log.party_size ?? 1) === 1 ? 'person' : 'people'}
          </Row>
          <Row icon={<Clock size={14} />} label="Observed">
            {log.observed_at ? ts(log.observed_at) : '—'}
          </Row>
          <Row icon={<Clock size={14} />} label="Submitted">
            {log.created_at ? ts(log.created_at) : '—'}
          </Row>
          <div className="pt-2 mt-2 border-t border-slate-100 text-[12px] text-slate-500">
            <span className="font-medium text-slate-600">{log.action}</span> by{' '}
            <span className="font-mono">{log.actor ?? '—'}</span> at {ts(log.ts)}
          </div>
        </div>
      </div>
    </div>
  )
}

function Chip({ label, tone }: { label: string; tone: 'blue' | 'amber' | 'emerald' | 'slate' }) {
  const cls: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    amber: 'bg-amber-50 text-amber-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    slate: 'bg-slate-100 text-slate-600',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${cls[tone]}`}>
      {label}
    </span>
  )
}

function Row({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-3 text-[13px]">
      <div className="text-slate-400 mt-0.5">{icon}</div>
      <div className="flex-1">
        <div className="text-slate-400 text-[11px] uppercase tracking-wide">{label}</div>
        <div className="text-slate-700">{children}</div>
      </div>
    </div>
  )
}
