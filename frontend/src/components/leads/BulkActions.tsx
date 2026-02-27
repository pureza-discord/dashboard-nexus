import { PhoneCall, Trophy, EyeOff, Trash2 } from 'lucide-react'

interface Props {
  count: number
  onMark: (status: string) => void
  onDelete: () => void
}

export default function BulkActions({ count, onMark, onDelete }: Props) {
  if (count === 0) return null

  return (
    <div className="flex items-center gap-3 bg-nexus-accent/10 border border-nexus-accent/20 rounded-xl px-4 py-2.5 animate-[slideIn_0.2s_ease]">
      <span className="text-sm text-nexus-accent font-medium">{count} selecionados</span>
      <div className="h-4 w-px bg-white/10" />
      <button onClick={() => onMark('contatado')} className="flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300 font-medium transition">
        <PhoneCall className="w-3.5 h-3.5" /> Contatado
      </button>
      <button onClick={() => onMark('fechado')} className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition">
        <Trophy className="w-3.5 h-3.5" /> Fechado
      </button>
      <button onClick={() => onMark('ignorado')} className="flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-300 font-medium transition">
        <EyeOff className="w-3.5 h-3.5" /> Ignorar
      </button>
      <div className="h-4 w-px bg-white/10" />
      <button onClick={onDelete} className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 font-medium transition">
        <Trash2 className="w-3.5 h-3.5" /> Excluir
      </button>
    </div>
  )
}
