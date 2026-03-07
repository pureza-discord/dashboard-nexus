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
    <div className="min-h-screen bg-nexus-bg">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="lg:pl-[240px]">
        <Header title={title} onOpenSidebar={() => setSidebarOpen(true)} />
        <main className="mx-auto w-full max-w-[1440px] px-4 py-5 md:px-6 md:py-7 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
