import { Menu } from 'lucide-react'

interface HeaderProps {
  title: string
  onOpenSidebar: () => void
}

export default function Header({ onOpenSidebar }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-black/90 backdrop-blur-sm">
      <div className="flex h-14 items-center px-6 lg:px-10">
        <button
          type="button"
          onClick={onOpenSidebar}
          className="mr-4 inline-flex h-8 w-8 items-center justify-center rounded-md text-[#666666] transition hover:text-white lg:hidden"
          aria-label="Abrir menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <span className="text-sm font-medium text-[#666666]">Nexus Leads Manager</span>
      </div>
    </header>
  )
}

