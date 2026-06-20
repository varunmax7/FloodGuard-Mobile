import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from '../components/ChartWrapper'
import { COLORS } from '../components/ChartWrapper'
import Layout from '../components/Layout'
import MapPanel from '../components/MapPanel'
import { adminApi } from '../api/client'
import maplibregl from 'maplibre-gl'

type Station = { station_id: string; name: string }
type Series  = { ts: string; obs_1h: number | null; pred_1h: number | null }
type Metrics = { mae_1h: number | null; bias_1h: number | null; corr_1h: number | null; n: number }
type Drill   = Series | null

function fmt(v: number | null | undefined) {
  return v == null ? '—' : v.toFixed(3)
}

function shortTs(iso: string) {
  const d = new Date(iso)
  return `${d.getDate()}/${d.getMonth()+1} ${String(d.getHours()).padStart(2,'0')}h`
}

// ── Error map wiring ──────────────────────────────────────────────────────────

function addErrorLayer(map: maplibregl.Map, geojson: GeoJSON.FeatureCollection) {
  if (map.getSource('error-pts')) return
  map.addSource('error-pts', { type: 'geojson', data: geojson })
  map.addLayer({
    id: 'error-circles',
    type: 'circle',
    source: 'error-pts',
    paint: {
      'circle-radius': 10,
      'circle-color': [
        'interpolate', ['linear'],
        ['get', 'diff_1h'],
        -5, '#22C55E',
        0,  '#FACC15',
        5,  '#EF4444',
      ],
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#fff',
      'circle-opacity': 0.85,
    },
  })

  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false })
  map.on('mouseenter', 'error-circles', (e) => {
    map.getCanvas().style.cursor = 'pointer'
    const f  = e.features?.[0]
    if (!f) return
    const p  = f.properties as { station_id: string; obs_1h: number; pred_1h: number; diff_1h: number }
    const ll = (f.geometry as GeoJSON.Point).coordinates as [number, number]
    popup.setLngLat(ll)
      .setHTML(`<div style="font:12px/1.4 sans-serif">
        <b>${p.station_id}</b><br/>
        Obs: ${p.obs_1h?.toFixed(2)} mm<br/>
        Pred: ${p.pred_1h?.toFixed(2)} mm<br/>
        Diff: <b style="color:${p.diff_1h > 0 ? '#EF4444' : '#22C55E'}">${p.diff_1h?.toFixed(2)} mm</b>
      </div>`)
      .addTo(map)
  })
  map.on('mouseleave', 'error-circles', () => {
    map.getCanvas().style.cursor = ''
    popup.remove()
  })
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ForecastVerificationPage() {
  const [stationId, setStationId] = useState<string>('')
  const [window_h,  setWindow]    = useState<number>(72)
  const [drill,     setDrill]     = useState<Drill>(null)

  const { data: stations = [] } = useQuery<Station[]>({
    queryKey: ['verify-stations'],
    queryFn:  adminApi.verifyStations,
  })

  const selectedId = stationId || stations[0]?.station_id

  const { data: ts_data, isLoading: tsLoading } = useQuery({
    queryKey: ['verify-timeseries', selectedId, window_h],
    queryFn:  () => adminApi.verifyTimeseries(selectedId, window_h),
    enabled:  !!selectedId,
  })

  const { data: errMetrics = [], isLoading: emLoading } = useQuery({
    queryKey: ['verify-errors', window_h],
    queryFn:  () => adminApi.verifyErrors(window_h),
  })

  const { data: errorMap } = useQuery({
    queryKey: ['verify-error-map'],
    queryFn:  adminApi.verifyErrorMap,
  })

  const series: Series[] = ts_data?.series ?? []
  const metrics: Metrics = ts_data?.metrics ?? {}
  const bf = ts_data?.bias_factor

  const chartData = series.map((s: Series) => ({
    ts:    shortTs(s.ts),
    'Obs (mm/h)':  s.obs_1h,
    'Pred (mm/h)': s.pred_1h,
  }))

  return (
    <Layout title="Forecast Verification">
      {/* ── Controls ── */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <select
          value={selectedId}
          onChange={e => setStationId(e.target.value)}
          className="px-3 py-1.5 rounded-lg border border-slate-200 text-[13px] bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {stations.map((s: Station) => (
            <option key={s.station_id} value={s.station_id}>{s.name} ({s.station_id})</option>
          ))}
        </select>
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-[12px] font-medium">
          {[24, 48, 72].map(h => (
            <button key={h}
              onClick={() => setWindow(h)}
              className={`px-3 py-1.5 transition-colors ${window_h === h ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}
            >{h}h</button>
          ))}
        </div>
      </div>

      {/* ── Main chart ── */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5 mb-5">
        <h3 className="text-[13px] font-semibold text-slate-700 mb-4">
          Rain 1h — Predicted vs Observed
        </h3>
        {tsLoading ? (
          <div className="h-48 flex items-center justify-center text-slate-400 text-sm">Loading…</div>
        ) : chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-slate-400 text-sm">No data in this window.</div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} onClick={(e: any) => e?.activePayload && setDrill(series[e.activeTooltipIndex])}>
              <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
              <XAxis dataKey="ts" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 10 }} unit=" mm" />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="Obs (mm/h)"  stroke={COLORS.blue}  dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="Pred (mm/h)" stroke={COLORS.high}  dot={false} strokeWidth={2} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>
        )}
        <p className="text-[11px] text-slate-400 mt-2">Click any point to drill down to raw values.</p>
      </div>

      {/* ── Metrics + bias ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        {[
          { label: 'MAE (1h)', value: fmt(metrics.mae_1h),  unit: 'mm' },
          { label: 'Bias (1h)', value: fmt(metrics.bias_1h), unit: 'mm' },
          { label: 'Correlation', value: fmt(metrics.corr_1h), unit: '' },
          { label: 'Bias factor ×', value: bf?.multiplier?.toFixed(3) ?? '—', unit: '' },
        ].map(({ label, value, unit }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-100 shadow-sm px-4 py-3">
            <div className="text-[11px] text-slate-400 font-medium">{label}</div>
            <div className="text-[22px] font-bold text-slate-900 mt-0.5">
              {value}<span className="text-[13px] text-slate-400 ml-1">{unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Error map + all-stations table (side by side) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        {/* Error map */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-[13px] font-semibold text-slate-700">Spatial Error Map (Pred − Obs mm/h)</h3>
            <div className="flex items-center gap-3 mt-1.5 text-[11px]">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-green-400 inline-block"/> Under-forecast</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-yellow-400 inline-block"/> On target</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full bg-red-400 inline-block"/> Over-forecast</span>
            </div>
          </div>
          <MapPanel
            className="w-full h-[320px]"
            onMapReady={(map) => {
              if (errorMap?.features?.length) {
                map.on('load', () => addErrorLayer(map, errorMap))
                if (map.loaded()) addErrorLayer(map, errorMap)
              }
            }}
          />
        </div>

        {/* All-stations metrics table */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <h3 className="text-[13px] font-semibold text-slate-700">All-Station Metrics</h3>
          </div>
          {emLoading ? (
            <div className="p-6 text-center text-sm text-slate-400">Loading…</div>
          ) : (
            <div className="overflow-y-auto max-h-[320px]">
              <table className="w-full text-[12px]">
                <thead className="bg-slate-50 sticky top-0">
                  <tr>
                    {['Station', 'MAE', 'Bias', 'Corr', 'n'].map(h => (
                      <th key={h} className="text-left px-3 py-2 font-medium text-slate-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {errMetrics.map((m: any) => (
                    <tr key={m.station_id}
                      onClick={() => setStationId(m.station_id)}
                      className={`cursor-pointer hover:bg-blue-50 ${m.station_id === selectedId ? 'bg-blue-50' : ''}`}
                    >
                      <td className="px-3 py-2 font-medium text-slate-800">{m.name}</td>
                      <td className="px-3 py-2 text-slate-600">{fmt(m.mae)}</td>
                      <td className="px-3 py-2" style={{ color: (m.bias ?? 0) > 0 ? '#EF4444' : '#22C55E' }}>{fmt(m.bias)}</td>
                      <td className="px-3 py-2 text-slate-600">{fmt(m.corr)}</td>
                      <td className="px-3 py-2 text-slate-400">{m.n}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Drill-down modal ── */}
      {drill && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setDrill(null)}>
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-80" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold text-slate-900 mb-3 text-[14px]">Raw values at {new Date(drill.ts).toLocaleString()}</h3>
            <table className="w-full text-[13px]">
              <thead><tr className="text-slate-400 text-left">
                <th className="pb-2">Field</th><th className="pb-2">Observed</th><th className="pb-2">Predicted</th>
              </tr></thead>
              <tbody className="divide-y divide-slate-50">
                {(['1h','3h','24h'] as const).map(k => (
                  <tr key={k}>
                    <td className="py-1.5 text-slate-500">Rain {k}</td>
                    <td className="py-1.5 font-mono">{(drill as any)[`obs_${k}`] ?? '—'}</td>
                    <td className="py-1.5 font-mono">{(drill as any)[`pred_${k}`] ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button onClick={() => setDrill(null)} className="mt-4 w-full py-2 rounded-lg bg-slate-100 text-[13px] font-medium text-slate-600 hover:bg-slate-200">Close</button>
          </div>
        </div>
      )}
    </Layout>
  )
}
