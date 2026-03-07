import {
  CalendarClock,
  CircleDollarSign,
  Globe,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Percent,
  User,
  X,
} from 'lucide-react'

import Badge from '../ui/Badge'
import { formatCurrency, formatDate, formatPhone } from '../../utils/format'

interface Props {
  lead: Record<string, unknown> | null
  onClose: () => void
}

function asText(value: unknown): string {
  if (value == null) return ''
  return String(value)
}

function getField(lead: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = asText(lead[key])
    if (value) return value
  }
  return ''
}

function Row({
  icon: Icon,
  label,
  value,
  href,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  href?: string
}) {
  if (!value) return null

  return (
    <div className="flex items-start gap-3 border-b border-white/[0.05] py-3 last:border-b-0">
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0 text-zinc-500" />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium text-nexus-muted">{label}</p>
        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className="break-all text-[13px] text-white transition-colors hover:text-zinc-300">
            {value}
          </a>
        ) : (
          <p className="break-all text-[13px] text-white">{value}</p>
        )}
      </div>
    </div>
  )
}

export default function LeadDetailModal({ lead, onClose }: Props) {
  if (!lead) return null

  const company = getField(lead, 'company_name', 'empresa')
  const city = getField(lead, 'city', 'cidade')
  const country = getField(lead, 'country', 'pais')
  const niche = getField(lead, 'niche', 'nicho')
  const phone = getField(lead, 'phone', 'telefone')
  const email = getField(lead, 'email')
  const website = getField(lead, 'website', 'site')
  const cleanPhone = formatPhone(phone)

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <div
        className="card relative max-h-[88vh] w-full max-w-lg overflow-y-auto shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-white/[0.06] p-5 md:p-6">
          <div>
            <h3 className="text-lg font-semibold text-white">{company || 'Lead'}</h3>
            <div className="mt-2 flex items-center gap-2">
              <Badge status={asText(lead.status) || 'novos'} />
              <span className="text-[12px] text-nexus-muted">{formatDate(asText(lead.created_at))}</span>
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-nexus-muted transition-colors hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-0 p-5 md:p-6">
          <Row icon={User} label="Empresa" value={company} />
          <Row icon={MapPin} label="Cidade" value={city} />
          <Row icon={Globe} label="Pais" value={country} />
          <Row icon={Globe} label="Nicho" value={niche} />
          <Row icon={Phone} label="Telefone" value={phone} href={cleanPhone ? `tel:${cleanPhone}` : undefined} />
          {cleanPhone ? (
            <Row
              icon={MessageCircle}
              label="WhatsApp"
              value={phone}
              href={`https://wa.me/${cleanPhone.replace('+', '')}`}
            />
          ) : null}
          <Row icon={Mail} label="Email" value={email} href={email ? `mailto:${email}` : undefined} />
          <Row icon={Globe} label="Site" value={website} href={website || undefined} />
          <Row icon={CircleDollarSign} label="Ticket estimado" value={formatCurrency(Number(lead.ticket_estimado || 0))} />
          <Row icon={Percent} label="Chance de fechamento" value={`${Number(lead.chance_fechamento || 0)}%`} />
          <Row icon={CalendarClock} label="Follow-up" value={formatDate(asText(lead.proximo_follow_up))} />
          <Row icon={CalendarClock} label="Ultimo contato" value={formatDate(asText(lead.ultimo_contato))} />
        </div>

        {asText(lead.observacoes) ? (
          <div className="px-5 pb-5 md:px-6 md:pb-6">
            <p className="mb-2 text-[11px] font-medium text-nexus-muted">Observacoes</p>
            <p className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2.5 text-[13px] text-zinc-300">
              {asText(lead.observacoes)}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  )
}
