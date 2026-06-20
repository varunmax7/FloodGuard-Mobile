import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

interface Props { title: string; children: ReactNode }

export default function Layout({ title, children }: Props) {
  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Topbar title={title} />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  )
}
