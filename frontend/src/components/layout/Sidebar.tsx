import { NavLink } from 'react-router-dom'
import { LayoutDashboard, BarChart3, LogOut } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
]

export default function Sidebar() {
  const { user, logout } = useAuth()

  return (
    <aside className="fixed inset-y-0 left-0 z-40 w-60 bg-nexus-sidebar border-r border-white/[0.06] flex flex-col">
      <div className="p-5 border-b border-white/[0.06]">
        <img
          src="/assets/logo2.png"
          alt="Nexus"
          className="h-8 object-contain"
          onError={(e) => {
            const el = e.target as HTMLImageElement
            el.style.display = 'none'
            el.parentElement!.innerHTML = '<span class="text-lg font-bold text-white">Nexus</span>'
          }}
        />
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-nexus-accent/10 text-nexus-accent'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]'
              }`
            }
          >
            <Icon className="w-[18px] h-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-white/[0.06]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-full bg-nexus-accent/20 text-nexus-accent text-xs font-bold flex items-center justify-center flex-shrink-0">
              {(user || 'A')[0].toUpperCase()}
            </div>
            <span className="text-sm text-zinc-400 truncate">{user}</span>
          </div>
          <button
            onClick={logout}
            className="text-zinc-500 hover:text-red-400 transition p-1"
            title="Sair"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}
