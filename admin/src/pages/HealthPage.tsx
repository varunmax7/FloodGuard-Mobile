import { useQuery } from '@tanstack/react-query'
import { CheckCircle, AlertTriangle, Wifi, WifiOff } from 'lucide-react'
import Layout from '../components/Layout'
import MapPanel from '../components/MapPanel'
import { adminApi } from '../api/client'
import maplibregl from 'maplibre-gl'

function age(h: number | null) {
  if (h == null) return 'never'
  if (h < 1) return `${Math.round(h * 60)}m ago`
  return `${h.toFixed(1)}h ago`
}

function addStationLayer(map: maplibregl.Map, stations: any[]) {
  if (!stations.length || map.getSource('stations')) return
  map.addSource('stations', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: stations.map(s => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: { name: s.name, up: s.up, last_obs: s.last_obs },
      })),
    },
  })
  map.addLayer({
    id: 'station-circles',
    type: 'circle',
    source: 'stations',
    paint: {
      'circle-radius': 8,
      'circle-color': ['case', ['get', 'up'], '#22C55E', '#EF4444'],
      'circle-stroke-width': 2,
      'circle-stroke-color': '#fff',
    },
  })
  const popup = new maplibregl.Popup({ closeButton: false })
  map.on('mouseenter', 'station-circles', (e) => {
    const f = e.features?.[0]; if (!f) return
    const p = f.properties as any
    const ll = (f.geometry as GeoJSON.Point).coordinates as [number, number]
    popup.setLngLat(ll)
      .setHTML(`<div style="font:12px sans-serif"><b>${p.name}</b><br/>${p.up ? '🟢 Up' : '🔴 Down'}<br/>${p.last_obs ? new Date(p.last_obs).toLocaleTimeString() : 'No data'}</div>`)
      .addTo(map)
  })
  map.on('mouseleave', 'station-circles', () => popup.remove())
}

export default function HealthPage() {
  const { data: feeds  = [], isLoading: fLoading } = useQuery({ queryKey: ['health-feeds'],    queryFn: adminApi.healthFeeds })
  const { data: stationsData = [] }                 = useQuery({ queryKey: ['health-stations'], queryFn: adminApi.healthStations })
  const { data: radarData }                         = useQuery({ queryKey: ['health-radar'],    queryFn: adminApi.healthRadar })

  const stale = (feeds as any[]).filter((f: any) => f.stale)

  return (
    <Layout title="System Health">

      {/* Feed status cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {fLoading ? (
          <div className="col-span-4 text-center text-slate-400 text-sm py-6">Loading…</div>
        ) : (feeds as any[]).map((f: any) => (
          <div key={f.feed} className={`bg-white rounded-xl border shadow-sm px-4 py-3 ${f.stale ? 'border-red-200' : 'border-slate-100'}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[12px] font-semibold text-slate-700 uppercase tracking-wide">{f.feed}</span>
              {f.stale
                ? <AlertTriangle size={14} className="text-red-500" />
                : <CheckCircle  size={14} className="text-emerald-500" />}
            </div>
            <div className={`text-[11px] font-medium ${f.stale ? 'text-red-500' : 'text-emerald-600'}`}>
              {f.stale ? '⚠ Stale' : '✓ Live'}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">{age(f.age_h)}</div>
            <div className="text-[11px] text-slate-400">{f.records_written} records</div>
            {f.last_error && <div className="text-[10px] text-red-400 mt-1 truncate">{f.last_error}</div>}
          </div>
        ))}
      </div>

      {stale.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-[13px] text-red-700 mb-6 flex items-center gap-2">
          <AlertTriangle size={15} />
          <strong>{stale.map((f: any) => f.feed).join(', ')}</strong> feed{stale.length > 1 ? 's are' : ' is'} stale — data may be outdated.
        </div>
      )}

      {/* Station uptime map + radar log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">

        {/* Station uptime map */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-slate-700">AWS Station Uptime</h3>
            <div className="flex gap-3 text-[11px]">
              <span className="flex items-center gap-1"><Wifi size={11} className="text-emerald-500"/>Up</span>
              <span className="flex items-center gap-1"><WifiOff size={11} className="text-red-500"/>Down</span>
            </div>
          </div>
          <MapPanel
            className="w-full h-[300px]"
            onMapReady={(map) => {
              const add = () => addStationLayer(map, stationsData as any[])
              if (map.loaded()) add(); else map.on('load', add)
            }}
          />
        </div>

        {/* Radar log */}
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-slate-700">Radar Frame Log</h3>
            <div className="flex gap-3 text-[11px] text-slate-400">
              <span>Frames: {radarData?.frame_count ?? 0}</span>
              <span className={radarData?.anomaly_count > 0 ? 'text-amber-600 font-semibold' : ''}>
                Anomalies: {radarData?.anomaly_count ?? 0}
              </span>
              <span className={radarData?.gaps?.length > 0 ? 'text-red-500 font-semibold' : ''}>
                Gaps: {radarData?.gaps?.length ?? 0}
              </span>
            </div>
          </div>
          <div className="overflow-y-auto max-h-[300px]">
            {radarData?.gaps?.length > 0 && radarData.gaps.map((g: any, i: number) => (
              <div key={i} className="px-4 py-2 bg-red-50 text-[11px] text-red-600 border-b border-red-100">
                ⚠ Gap {g.gap_min}min: {new Date(g.from).toLocaleTimeString()} → {new Date(g.to).toLocaleTimeString()}
              </div>
            ))}
            <table className="w-full text-[11px]">
              <thead className="bg-slate-50 sticky top-0">
                <tr>
                  <th className="text-left px-3 py-2 text-slate-500">Time</th>
                  <th className="text-left px-3 py-2 text-slate-500">dBZ max</th>
                  <th className="text-left px-3 py-2 text-slate-500">Anomaly</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {(radarData?.frames ?? []).map((f: any) => (
                  <tr key={f.ts} className={f.anomaly ? 'bg-amber-50' : ''}>
                    <td className="px-3 py-1.5 text-slate-500">{new Date(f.ts).toLocaleTimeString()}</td>
                    <td className="px-3 py-1.5 font-mono">{f.dbz_max?.toFixed(1)}</td>
                    <td className="px-3 py-1.5">{f.anomaly ? <span className="text-amber-600 font-semibold">⚠ Yes</span> : <span className="text-slate-300">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>

    </Layout>
  )
}
