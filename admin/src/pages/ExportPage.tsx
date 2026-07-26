import { useState } from 'react'
import { Download } from 'lucide-react'
import Layout from '../components/Layout'

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'

function buildUrl(type: string, format: string, from: string, to: string) {
  const p = new URLSearchParams({ type, fmt: format })
  if (from) p.set('from', new Date(from).toISOString())
  if (to)   p.set('to',   new Date(to).toISOString())
  return `${BASE}/admin/export/?${p}`
}

export default function ExportPage() {
  const [type,   setType]   = useState('reports')
  const [format, setFormat] = useState('csv')
  const [from,   setFrom]   = useState('')
  const [to,     setTo]     = useState('')

  function download() {
    const token = localStorage.getItem('fg_admin_access')
    const url   = buildUrl(type, format, from, to)
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `${type}.${format === 'geojson' ? 'geojson' : 'csv'}`
        a.click()
      })
  }

  return (
    <Layout title="Historical Export">
      <div className="max-w-xl mx-auto flex flex-col gap-5">

        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-6 flex flex-col gap-5">

          {/* Dataset type */}
          <div>
            <label className="block text-[12px] font-semibold text-slate-600 mb-2">Dataset</label>
            <div className="flex gap-2">
              {['reports','risk'].map(t => (
                <button key={t} onClick={() => setType(t)}
                  className={`px-4 py-2 rounded-lg text-[12px] font-semibold border transition-colors ${type===t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}>
                  {t === 'reports' ? 'Flood Reports' : 'Risk Snapshots'}
                </button>
              ))}
            </div>
          </div>

          {/* Format */}
          <div>
            <label className="block text-[12px] font-semibold text-slate-600 mb-2">Format</label>
            <div className="flex gap-2">
              {['csv','geojson'].map(f => (
                <button key={f} onClick={() => setFormat(f)}
                  className={`px-4 py-2 rounded-lg text-[12px] font-semibold border transition-colors ${format===f ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'}`}>
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Date range */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[12px] font-semibold text-slate-600 mb-1">From</label>
              <input type="date" value={from} onChange={e => setFrom(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-[12px] font-semibold text-slate-600 mb-1">To</label>
              <input type="date" value={to} onChange={e => setTo(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>

          <button onClick={download}
            className="flex items-center justify-center gap-2 py-2.5 rounded-xl text-[13px] font-semibold text-white bg-blue-600 hover:bg-blue-700 transition-colors">
            <Download size={15} />
            Download {type === 'reports' ? 'Flood Reports' : 'Risk Snapshots'} ({format.toUpperCase()})
          </button>

        </div>

        <div className="bg-slate-50 rounded-xl border border-slate-100 px-4 py-3 text-[12px] text-slate-500">
          <p className="font-semibold text-slate-600 mb-1">Use cases</p>
          <ul className="list-disc list-inside space-y-0.5">
            <li>ASDMA/NDMA operational reporting</li>
            <li>Insurance loss-validation datasets</li>
            <li>ML training data extraction</li>
            <li>GIS analysis in QGIS / ArcGIS</li>
          </ul>
        </div>

      </div>
    </Layout>
  )
}
