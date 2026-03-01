const styles: Record<string, string> = {
  novos: 'text-white bg-white/[0.08]',
  contatados: 'text-[#999999] bg-white/[0.05]',
  proposta: 'text-[#bbbbbb] bg-white/[0.06]',
  fechados: 'text-nexus-green bg-nexus-green/10',
  perdidos: 'text-nexus-red bg-nexus-red/10',
}

function formatStatus(status: string): string {
  if (!status) return 'Novos'
  return status.charAt(0).toUpperCase() + status.slice(1)
}

export default function Badge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold ${styles[status] || styles.novos}`}>
      {formatStatus(status)}
    </span>
  )
}
