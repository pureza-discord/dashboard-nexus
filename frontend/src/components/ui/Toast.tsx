import { useState, createContext, useContext, useCallback, type ReactNode } from 'react'
import { CheckCircle, AlertCircle, X } from 'lucide-react'

interface ToastItem { id: number; message: string; type: 'ok' | 'error' }

const Ctx = createContext<(msg: string, type?: 'ok' | 'error') => void>(() => {})

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((message: string, type: 'ok' | 'error' = 'ok') => {
    const id = nextId++
    setItems((prev) => [...prev, { id, message, type }])
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 3500)
  }, [])

  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="fixed top-4 right-4 z-50 space-y-2 pointer-events-none">
        {items.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-xl text-sm font-medium animate-[slideIn_0.3s_ease] ${
              t.type === 'ok'
                ? 'bg-emerald-500/90 text-white'
                : 'bg-red-500/90 text-white'
            }`}
          >
            {t.type === 'ok' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            {t.message}
            <button onClick={() => setItems((p) => p.filter((x) => x.id !== t.id))} className="ml-2 opacity-70 hover:opacity-100">
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}

export const useToast = () => useContext(Ctx)
