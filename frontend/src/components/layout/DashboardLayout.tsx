import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function DashboardLayout() {
  return (
    <div className="min-h-screen bg-nexus-bg">
      <Sidebar />
      <div className="ml-60">
        <Outlet />
      </div>
    </div>
  )
}
