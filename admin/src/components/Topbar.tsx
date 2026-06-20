import { Bell, RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

interface Props { title: string }

export default function Topbar({ title }: Props) {
  const qc = useQueryClient()

  return (
    <header className="h-14 border-b border-slate-100 bg-white flex items-center justify-between px-6 flex-shrink-0">
      <div className="flex items-center gap-3">
        <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
        <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200">
          Hyderabad
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => qc.invalidateQueries()}
          className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
          title="Refresh all data"
        >
          <RefreshCw size={15} />
        </button>
        <button className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors">
          <Bell size={15} />
        </button>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-400 ml-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          System Online
        </div>
      </div>
    </header>
  )
}
