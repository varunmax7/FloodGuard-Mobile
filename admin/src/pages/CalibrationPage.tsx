import { useState } from 'react'
import Layout from '../components/Layout'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Save, History } from 'lucide-react'

export default function CalibrationPage() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const isAdmin = user?.role === 'ADMIN'

  const { data: weights } = useQuery({
    queryKey: ['calibration-weights'],
    queryFn: adminApi.getWeights,
    retry: false,
  })
  const { data: auditLog } = useQuery({
    queryKey: ['audit-calibration'],
    queryFn: adminApi.auditCalibration,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: (data: object) => adminApi.putWeights(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['audit-calibration'] }),
  })

  const [testPayload, setTestPayload] = useState('{"change_type":"test","twi_weight":0.25}')

  return (
    <Layout title="Calibration Console">
      <div className="max-w-4xl mx-auto flex flex-col gap-6">
        {!isAdmin && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-[13px] text-amber-700">
            🔒 You have <strong>read-only</strong> access. ADMIN role required to modify weights.
          </div>
        )}

        {/* Current weights */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold text-slate-900">FSI Weights (current)</h3>
            <span className="text-[11px] text-slate-400">Full editor — Phase 12</span>
          </div>
          <div className="px-5 py-4 text-[13px] text-slate-500 font-mono bg-slate-50 rounded-b-xl">
            {weights ? JSON.stringify(weights, null, 2) : 'Loading…'}
          </div>
        </div>

        {/* Test PUT (admin only) */}
        {isAdmin && (
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
            <div className="px-5 py-4 border-b border-slate-100">
              <h3 className="text-[14px] font-semibold text-slate-900">Test Calibration Write</h3>
              <p className="text-[12px] text-slate-500 mt-0.5">Sends a PUT — writes a CalibrationLog entry.</p>
            </div>
            <div className="p-5 flex flex-col gap-3">
              <textarea
                value={testPayload}
                onChange={(e) => setTestPayload(e.target.value)}
                rows={3}
                className="w-full font-mono text-[12px] px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={() => mutation.mutate(JSON.parse(testPayload))}
                disabled={mutation.isPending}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold text-white self-start"
                style={{ background: '#2563EB' }}
              >
                <Save size={14} />
                {mutation.isPending ? 'Saving…' : 'Save & Log'}
              </button>
              {mutation.isSuccess && (
                <p className="text-[12px] text-emerald-600">✓ Saved and audit log written.</p>
              )}
            </div>
          </div>
        )}

        {/* Audit log */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
            <History size={15} className="text-slate-400" />
            <h3 className="text-[14px] font-semibold text-slate-900">Calibration Audit Log</h3>
          </div>
          <div className="divide-y divide-slate-50">
            {Array.isArray(auditLog) && auditLog.length > 0 ? auditLog.map((l: any, i: number) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-[13px]">
                <div>
                  <span className="font-medium text-slate-700">{l.change_type}</span>
                  <span className="text-slate-400 ml-2">by {l.actor}</span>
                </div>
                <span className="text-[11px] text-slate-400">
                  {new Date(l.ts).toLocaleString()}
                </span>
              </div>
            )) : (
              <div className="px-5 py-6 text-center text-[13px] text-slate-400">
                No calibration changes recorded yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  )
}
