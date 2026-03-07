import { CheckCircle, X, XCircle } from 'lucide-react'
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
    }, 4000)
  }, [])

  const dismiss = (id: number) => {
    setItems((prev) => prev.filter((item) => item.id !== id))
  }

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[80] flex w-[min(92vw,360px)] flex-col gap-2">
        {items.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-[13px] shadow-lg backdrop-blur-sm transition-all ${
              toast.type === 'ok'
                ? 'border-emerald-500/20 bg-emerald-950/80 text-emerald-300'
                : 'border-red-500/20 bg-red-950/80 text-red-300'
            }`}
          >
            {toast.type === 'ok' ? (
              <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 opacity-70" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 opacity-70" />
            )}
            <span className="flex-1 leading-snug">{toast.message}</span>
            <button type="button" onClick={() => dismiss(toast.id)} className="mt-0.5 opacity-50 transition hover:opacity-100">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
