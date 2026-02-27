const styles: Record<string, string> = {
  novo: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  contatado: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  fechado: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  ignorado: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20',
}

export default function Badge({ status }: { status: string }) {
  return (
    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${styles[status] || styles.novo}`}>
      {status}
    </span>
  )
}
