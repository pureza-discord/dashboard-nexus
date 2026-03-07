import { Menu } from 'lucide-react'

interface HeaderProps {
  title: string
  onOpenSidebar: () => void
}

export default function Header({ title, onOpenSidebar }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-nexus-bg/80 backdrop-blur-xl">
      <div className="flex h-14 items-center justify-between px-4 md:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onOpenSidebar}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-nexus-muted transition-colors hover:bg-white/[0.06] hover:text-white lg:hidden"
            aria-label="Abrir menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="text-sm font-semibold text-white">{title}</h1>
        </div>
      </div>
    </header>
  )
}
