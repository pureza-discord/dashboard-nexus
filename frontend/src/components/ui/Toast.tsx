import { X } from 'lucide-react'
import { createContext, type ReactNode, useCallback, useContext, useState } from 'react'

type ToastType = 'ok' | 'error'

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

type PushToast = (message: string, type?: ToastType) => void

const ToastContext = createContext<PushToast>(() => {})
let nextId = 1

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((message: string, type: ToastType = 'ok') => {
    const id = nextId++
    setItems((prev) => [...prev, { id, message, type }])
    window.setTimeout(() => {
      setItems((prev) => prev.filter((item) => item.id !== id))
    }, 3600)
  }, [])

  const dismiss = (id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id))
  }

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[80] flex w-[min(92vw,340px)] flex-col gap-2">
        {items.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2.5 text-[13px] shadow-lg ${
              toast.type === 'ok'
                ? 'border-nexus-green/20 bg-nexus-green/10 text-nexus-green'
                : 'border-nexus-red/20 bg-nexus-red/10 text-nexus-red'
            }`}
          >
            <span className="flex-1">{toast.message}</span>
            <button type="button" onClick={() => dismiss(toast.id)} className="mt-0.5 opacity-60 transition hover:opacity-100">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
