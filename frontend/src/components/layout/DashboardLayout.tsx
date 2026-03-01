import { useMemo, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'

function getTitle(pathname: string): string {
  if (pathname.startsWith('/app/leads')) return 'Leads'
  if (pathname.startsWith('/app/conta')) return 'Conta'
  return 'Dashboard'
}

export default function DashboardLayout() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const title = useMemo(() => getTitle(location.pathname), [location.pathname])

  return (
    <div className="min-h-screen bg-black">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-[220px]">
        <Header title={title} onOpenSidebar={() => setSidebarOpen(true)} />
        <main className="mx-auto w-full max-w-[1400px] px-6 py-8 lg:px-10 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
