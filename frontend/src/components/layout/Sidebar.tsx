import { NavLink } from 'react-router-dom'
import { LayoutDashboard, LogOut, Users, UserCircle } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

const links = [
  { to: '/app/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/app/leads', icon: Users, label: 'Leads' },
  { to: '/app/conta', icon: UserCircle, label: 'Conta' },
]

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { logout } = useAuth()

  return (
    <>
      {open ? (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/80 lg:hidden"
          onClick={onClose}
          aria-label="Fechar menu"
        />
      ) : null}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[220px] flex-col border-r border-white/[0.06] bg-[#050505] transition-transform duration-200 lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center px-6">
          <span className="text-base font-bold tracking-tight text-white">Nexus Leads Manager</span>
        </div>

        <nav className="flex-1 px-3 pt-2">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium transition-colors ${
                  isActive
                    ? 'bg-white/[0.06] text-white'
                    : 'text-[#666666] hover:text-[#999999]'
                }`
              }
            >
              <Icon className="h-[18px] w-[18px]" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/[0.06] p-3">
          <button
            type="button"
            onClick={() => {
              void logout()
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] font-medium text-[#666666] transition-colors hover:text-[#999999]"
          >
            <LogOut className="h-[18px] w-[18px]" />
            Sair
          </button>
        </div>
      </aside>
    </>
  )
}

