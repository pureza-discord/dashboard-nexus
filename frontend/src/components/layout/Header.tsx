import { useEffect, useState } from 'react'
import { Circle } from 'lucide-react'

export default function Header({ title }: { title: string }) {
  const [apiOk, setApiOk] = useState(true)

  useEffect(() => {
    const check = () =>
      fetch('/api/me', { headers: { Authorization: `Bearer ${localStorage.getItem('nexus_token') || ''}` } })
        .then((r) => setApiOk(r.ok || r.status === 401))
        .catch(() => setApiOk(false))
    check()
    const id = setInterval(check, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="h-14 border-b border-white/[0.06] bg-nexus-surface/50 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-20">
      <h2 className="text-base font-semibold text-white">{title}</h2>
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <Circle className={`w-2 h-2 fill-current ${apiOk ? 'text-emerald-400' : 'text-red-400'}`} />
        API {apiOk ? 'Online' : 'Offline'}
      </div>
    </header>
  )
}
