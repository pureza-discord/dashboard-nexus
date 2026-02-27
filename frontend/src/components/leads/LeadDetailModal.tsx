import { X, Phone, Mail, Globe, MapPin, MessageCircle, Instagram, Linkedin, Star } from 'lucide-react'
import Badge from '../ui/Badge'
import { formatPhone, formatDate } from '../../utils/format'

interface Props {
  lead: Record<string, any> | null
  onClose: () => void
}

function Row({ icon: Icon, label, value, href }: { icon: any; label: string; value: string; href?: string }) {
  if (!value) return null
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-white/[0.04]">
      <Icon className="w-4 h-4 text-zinc-500 mt-0.5 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-[11px] text-zinc-500 uppercase tracking-wider">{label}</p>
        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className="text-sm text-nexus-accent hover:text-blue-400 transition break-all">
            {value}
          </a>
        ) : (
          <p className="text-sm text-zinc-200 break-all">{value}</p>
        )}
      </div>
    </div>
  )
}

export default function LeadDetailModal({ lead, onClose }: Props) {
  if (!lead) return null
  const tel = lead.telefone || ''
  const cleanTel = formatPhone(tel)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative bg-nexus-card border border-white/[0.08] rounded-2xl shadow-2xl shadow-black/40 w-full max-w-lg max-h-[85vh] overflow-y-auto animate-[fadeIn_0.2s_ease]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-white/[0.06]">
          <div>
            <h3 className="text-lg font-bold text-white">{lead.nome_empresa || 'Lead'}</h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge status={lead._status} />
              <span className="text-xs text-zinc-600">{formatDate(lead._created)}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-0">
          <Row icon={MapPin} label="Endereço" value={lead.endereco} />
          <Row icon={MapPin} label="Cidade" value={lead.cidade} />
          <Row icon={Phone} label="Telefone" value={tel} href={cleanTel ? `tel:${cleanTel}` : undefined} />
          {cleanTel && <Row icon={MessageCircle} label="WhatsApp" value={tel} href={`https://wa.me/${cleanTel.replace('+', '')}`} />}
          <Row icon={Mail} label="Email" value={lead.email} href={lead.email ? `mailto:${lead.email}` : undefined} />
          <Row icon={Globe} label="Site" value={lead.site} href={lead.site} />
          <Row icon={Instagram} label="Instagram" value={lead.instagram} href={lead.instagram} />
          <Row icon={Linkedin} label="LinkedIn" value={lead.linkedin} href={lead.linkedin} />
          <Row icon={Star} label="Rating" value={lead.rating} />
          <Row icon={Star} label="Reviews" value={lead.reviews_count} />
          <Row icon={Globe} label="País" value={lead.pais} />
          <Row icon={Globe} label="Nicho" value={lead.nicho} />
          {lead.coordinates && <Row icon={MapPin} label="Coordenadas" value={lead.coordinates} />}
          {lead.fonte_link && <Row icon={Globe} label="Fonte" value="Abrir no Google Maps" href={lead.fonte_link} />}
        </div>

        {lead.observacoes && (
          <div className="px-5 pb-5">
            <p className="text-[11px] text-zinc-500 uppercase tracking-wider mb-1">Observações</p>
            <p className="text-xs text-zinc-400 bg-zinc-900/50 rounded-lg px-3 py-2">{lead.observacoes}</p>
          </div>
        )}
      </div>
    </div>
  )
}
