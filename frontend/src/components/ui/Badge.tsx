import { cn } from '../../lib/utils'

const styles: Record<string, string> = {
  novos: 'text-blue-300 bg-blue-500/10 border-blue-500/20',
  contatados: 'text-nexus-muted bg-white/[0.06] border-white/[0.08]',
  proposta: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
  fechados: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  perdidos: 'text-red-400 bg-red-500/10 border-red-500/20',
}

function formatStatus(status: string): string {
  if (!status) return 'Novos'
  return status.charAt(0).toUpperCase() + status.slice(1)
}

export default function Badge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold',
        styles[status] || styles.novos,
      )}
    >
      {formatStatus(status)}
    </span>
  )
}
