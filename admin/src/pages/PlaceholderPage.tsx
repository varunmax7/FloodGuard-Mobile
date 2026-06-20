import Layout from '../components/Layout'
import { Construction } from 'lucide-react'

interface Props { title: string; section: string; phase: string; description?: string }

export default function PlaceholderPage({ title, section, phase, description }: Props) {
  return (
    <Layout title={title}>
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center">
          <Construction size={28} className="text-slate-400" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-900">{section}</h2>
          {description && <p className="text-sm text-slate-500 mt-1 max-w-sm">{description}</p>}
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100">
          Full implementation in {phase}
        </span>
      </div>
    </Layout>
  )
}
