import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { type ReactNode } from 'react'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Leads from './pages/Leads'
import Account from './pages/Account'
import DashboardLayout from './components/layout/DashboardLayout'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
      </div>
    )
  }
  if (user) return <>{children}</>
  const next = encodeURIComponent(`${location.pathname}${location.search}`)
  return <Navigate to={`/login?next=${next}`} replace />
}

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white/60" />
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/" element={<Navigate to={user ? '/app/dashboard' : '/login'} replace />} />
      <Route path="/login" element={user ? <Navigate to="/app/dashboard" replace /> : <Login />} />
      <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
        <Route path="/app" element={<Navigate to="/app/dashboard" replace />} />
        <Route path="/app/dashboard" element={<Dashboard />} />
        <Route path="/app/leads" element={<Leads />} />
        <Route path="/app/conta" element={<Account />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? '/app/dashboard' : '/login'} replace />} />
    </Routes>
  )
}
