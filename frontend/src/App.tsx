import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Analytics from './pages/Analytics'
import DashboardLayout from './components/layout/DashboardLayout'
import { Loader2 } from 'lucide-react'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-nexus-bg">
        <Loader2 className="w-8 h-8 text-nexus-accent animate-spin" />
      </div>
    )
  }
  return user ? <>{children}</> : <Navigate to="/login" />
}

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-nexus-bg">
        <Loader2 className="w-8 h-8 text-nexus-accent animate-spin" />
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" /> : <Login />} />
      <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analytics" element={<Analytics />} />
      </Route>
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}
