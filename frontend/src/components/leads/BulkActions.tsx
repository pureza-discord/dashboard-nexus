import { PhoneCall, Trash2, Trophy, XCircle } from 'lucide-react'

interface Props {
  count: number
  onMark: (status: string) => void
  onDelete: () => void
}

export default function BulkActions({ count, onMark, onDelete }: Props) {
  if (count === 0) return null

  return (
    <div className="inline-flex flex-wrap items-center gap-2 rounded-lg border border-white/[0.08] bg-nexus-card px-3 py-2">
      <span className="mr-1 text-[13px] font-medium text-white">{count} selecionados</span>
      <ActionBtn onClick={() => onMark('contatados')} icon={PhoneCall} label="Contatado" />
      <ActionBtn onClick={() => onMark('fechados')} icon={Trophy} label="Fechado" />
      <ActionBtn onClick={() => onMark('perdidos')} icon={XCircle} label="Perdido" />
      <ActionBtn onClick={onDelete} icon={Trash2} label="Excluir" danger />
    </div>
  )
}

function ActionBtn({
  onClick,
  icon: Icon,
  label,
  danger,
}: {
  onClick: () => void
  icon: React.ComponentType<{ className?: string }>
  label: string
  danger?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] px-2.5 py-1 text-[12px] font-medium transition-colors hover:border-white/[0.15] ${
        danger ? 'text-red-400 hover:text-red-300' : 'text-nexus-muted hover:text-white'
      }`}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}
