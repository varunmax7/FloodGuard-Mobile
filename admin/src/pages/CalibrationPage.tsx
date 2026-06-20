import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, FlaskConical, RotateCcw } from 'lucide-react'
import Layout from '../components/Layout'
import { adminApi } from '../api/client'
import { useAuth } from '../auth/AuthContext'

const LAYERS = [
  { key: 'twi',              label: 'TWI (Topographic Wetness)' },
  { key: 'depression_depth', label: 'Depression Depth' },
  { key: 'hand',             label: 'HAND (Height Above Nearest Drainage)' },
  { key: 'dist_to_water',    label: 'Distance to Water' },
  { key: 'slope',            label: 'Slope' },
  { key: 'imperviousness',   label: 'Imperviousness' },
] as const

type WeightsKey = typeof LAYERS[number]['key']
type Weights = Record<string, number>

function fmt3(v: number) { return v.toFixed(3) }

export default function CalibrationPage() {
  const { user }  = useAuth()
  const qc        = useQueryClient()
  const isAdmin   = user?.role === 'ADMIN'

  const { data: current, isLoading } = useQuery<Weights>({
    queryKey: ['calibration-weights'],
    queryFn:  adminApi.getWeights,
  })

  const { data: auditLog = [] } = useQuery({
    queryKey: ['audit-calibration'],
    queryFn:  adminApi.auditCalibration,
  })

  const [draft, setDraft]           = useState<Weights | null>(null)
  const [preview, setPreview]       = useState<any>(null)
  const [backtest, setBacktest]     = useState<any>(null)
  const [previewDate, setPreviewDate] = useState('')

  const w: Weights = draft ?? current ?? {}

  function set(key: string, val: number) {
    setDraft(prev => ({ ...(prev ?? current ?? {}), [key]: val }))
    setPreview(null); setBacktest(null)
  }

  const total = LAYERS.reduce((s, l) => s + (Number(w[l.key]) || 0), 0)
  const totalOk = Math.abs(total - 1.0) < 0.01

  const saveMut = useMutation({
    mutationFn: () => adminApi.putWeights(w),
    onSuccess:  () => {
      qc.invalidateQueries({ queryKey: ['calibration-weights'] })
      qc.invalidateQueries({ queryKey: ['audit-calibration'] })
      setDraft(null)
    },
  })

  const previewMut = useMutation({
    mutationFn: () => adminApi.calibratePreview(w, previewDate || undefined),
    onSuccess:  (data) => setPreview(data),
  })

  const backtestMut = useMutation({
    mutationFn: () => adminApi.calibrateBacktest(w),
    onSuccess:  (data) => setBacktest(data),
  })

  if (isLoading) return <Layout title="Calibration Console"><div className="p-8 text-center text-slate-400">Loading…</div></Layout>

  return (
    <Layout title="Calibration Console">
      <div className="max-w-5xl mx-auto flex flex-col gap-6">

        {!isAdmin && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-[13px] text-amber-700">
            🔒 Read-only — ADMIN role required to commit weights.
          </div>
        )}

        {/* FSI layer weights */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-[14px] font-semibold text-slate-900">FSI Layer Weights</h3>
              <p className="text-[11px] text-slate-400 mt-0.5">Must sum to 1.00</p>
            </div>
            <span className={`text-[13px] font-bold px-3 py-1 rounded-full ${totalOk ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
              Σ = {fmt3(total)}
            </span>
          </div>
          <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
            {LAYERS.map(({ key, label }) => (
              <div key={key}>
                <div className="flex justify-between text-[12px] mb-1">
                  <span className="text-slate-600 font-medium">{label}</span>
                  <span className="font-mono text-slate-900">{fmt3(Number(w[key]) || 0)}</span>
                </div>
                <input
                  type="range" min={0} max={1} step={0.01}
                  value={Number(w[key]) || 0}
                  onChange={e => set(key, parseFloat(e.target.value))}
                  disabled={!isAdmin}
                  className="w-full accent-blue-600"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Risk thresholds + hazard cutoffs */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-[13px] font-semibold text-slate-700 mb-3">Risk Matrix Thresholds (FSI score)</h3>
            {(['threshold_low','threshold_moderate','threshold_high'] as const).map(k => (
              <div key={k} className="flex items-center gap-3 mb-2">
                <span className="text-[12px] text-slate-500 w-28">{k.replace('threshold_','').toUpperCase()}</span>
                <input type="number" step="0.01" min={0} max={1}
                  value={Number(w[k] ?? 0).toFixed(2)}
                  onChange={e => set(k, parseFloat(e.target.value))}
                  disabled={!isAdmin}
                  className="w-24 px-2 py-1 border border-slate-200 rounded text-[12px] font-mono text-right focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}
          </div>
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-[13px] font-semibold text-slate-700 mb-3">Hazard Cutoffs (mm/h)</h3>
            {(['hazard_low','hazard_moderate','hazard_high'] as const).map(k => (
              <div key={k} className="flex items-center gap-3 mb-2">
                <span className="text-[12px] text-slate-500 w-28">{k.replace('hazard_','').toUpperCase()}</span>
                <input type="number" step="0.5" min={0}
                  value={Number(w[k] ?? 0).toFixed(1)}
                  onChange={e => set(k, parseFloat(e.target.value))}
                  disabled={!isAdmin}
                  className="w-24 px-2 py-1 border border-slate-200 rounded text-[12px] font-mono text-right focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-[11px] text-slate-400">mm/h</span>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex items-center gap-2">
            <input type="date" value={previewDate} onChange={e => setPreviewDate(e.target.value)}
              className="px-3 py-1.5 border border-slate-200 rounded-lg text-[12px] focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button onClick={() => previewMut.mutate()} disabled={previewMut.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-slate-100 text-slate-700 hover:bg-slate-200">
              <FlaskConical size={13} />{previewMut.isPending ? 'Computing…' : 'Preview'}
            </button>
          </div>
          <button onClick={() => backtestMut.mutate()} disabled={backtestMut.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-violet-50 text-violet-700 hover:bg-violet-100">
            <RotateCcw size={13} />{backtestMut.isPending ? 'Running…' : 'Backtest vs floods'}
          </button>
          {isAdmin && (
            <button onClick={() => saveMut.mutate()}
              disabled={saveMut.isPending || !totalOk || !draft}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[12px] font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-40 ml-auto">
              <Save size={13} />{saveMut.isPending ? 'Saving…' : 'Commit & Audit'}
            </button>
          )}
        </div>
        {saveMut.isSuccess && <p className="text-[12px] text-emerald-600">✓ Weights committed and audit log written.</p>}

        {/* Preview result */}
        {preview && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-[13px] font-semibold text-slate-700 mb-2">Preview Results</h3>
            <div className="flex gap-6 text-[13px] mb-3">
              <span>Total hexes: <b>{preview.total_hexes}</b></span>
              <span className={preview.changed > 0 ? 'text-amber-600 font-semibold' : 'text-emerald-600'}>
                Changed: {preview.changed}
              </span>
            </div>
            {preview.preview?.filter((r: any) => r.changed).slice(0, 10).map((r: any) => (
              <div key={r.h3_index} className="text-[12px] py-1 border-b border-slate-50 flex gap-4">
                <span className="text-slate-500 w-28 truncate">{r.ward_name || r.h3_index.slice(0,8)}</span>
                <span className="text-slate-400">{r.current_risk} → <b className="text-slate-700">{r.new_risk}</b></span>
                <span className="text-slate-300">FSI {r.current_fsi} → {r.new_fsi}</span>
              </div>
            ))}
          </div>
        )}

        {/* Backtest result */}
        {backtest && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-[13px] font-semibold text-slate-700 mb-3">Backtest vs Known Floods (VERIFIED reports)</h3>
            <div className="flex gap-6 text-[13px] mb-3">
              <span>Total: <b>{backtest.total}</b></span>
              <span className="text-emerald-600">Correct: <b>{backtest.correct}</b></span>
              <span className="text-red-500">Incorrect: <b>{backtest.incorrect}</b></span>
              <span className="font-bold">Accuracy: {((backtest.accuracy ?? 0)*100).toFixed(0)}%</span>
            </div>
          </div>
        )}

        {/* Audit log */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100">
            <h3 className="text-[13px] font-semibold text-slate-700">Calibration Audit Log</h3>
          </div>
          <div className="divide-y divide-slate-50">
            {auditLog.length === 0 ? (
              <div className="px-5 py-6 text-center text-[13px] text-slate-400">No calibration changes yet.</div>
            ) : auditLog.map((l: any, i: number) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-[13px]">
                <div>
                  <span className="font-medium text-slate-700">{l.change_type}</span>
                  <span className="text-slate-400 ml-2">by {l.actor}</span>
                </div>
                <span className="text-[11px] text-slate-400">{new Date(l.ts).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </Layout>
  )
}
