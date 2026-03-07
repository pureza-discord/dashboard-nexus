import { ChevronDown, ChevronUp, Globe, Mail, Phone, Star, Trash2 } from 'lucide-react'

import type { LeadItem, LeadStatus } from '../../hooks/useLeads'
import { formatCurrency, formatPhone, truncate } from '../../utils/format'
import Badge from '../ui/Badge'
import { SkeletonTable } from '../ui/Skeleton'

interface Props {
  leads: LeadItem[]
  loading: boolean
  selected: Set<string>
  onSelect: (id: string) => void
  onSelectAll: () => void
  onPatch: (id: string, payload: Record<string, unknown>) => void
  onDelete: (id: string) => void
  onDetail: (id: string) => void
  sortBy: string
  sortDir: string
  onSort: (col: string) => void
}

const columns = [
  { key: 'status', label: 'Status', width: 'w-28', sortable: true },
  { key: 'empresa', label: 'Empresa', width: 'min-w-[220px]', sortable: true },
  { key: 'telefone', label: 'Telefone', width: 'w-44', sortable: false },
  { key: 'email', label: 'Email', width: 'w-52', sortable: false },
  { key: 'site', label: 'Site', width: 'w-56', sortable: false },
  { key: 'rating', label: 'Rating', width: 'w-24', sortable: true },
  { key: 'cidade', label: 'Cidade', width: 'w-36', sortable: true },
  { key: 'ticket_estimado', label: 'Ticket', width: 'w-34', sortable: true },
  { key: 'chance_fechamento', label: 'Chance', width: 'w-26', sortable: true },
  { key: 'proximo_follow_up', label: 'Follow-up', width: 'w-40', sortable: false },
  { key: 'ultimo_contato', label: 'Ultimo contato', width: 'w-40', sortable: false },
  { key: 'observacoes', label: 'Observacoes', width: 'w-52', sortable: false },
]

const statusOptions: { value: LeadStatus; label: string }[] = [
  { value: 'novos', label: 'Novos' },
  { value: 'contatados', label: 'Contatados' },
  { value: 'proposta', label: 'Proposta' },
  { value: 'fechados', label: 'Fechados' },
  { value: 'perdidos', label: 'Perdidos' },
]

function SortIcon({ col, sortBy, sortDir }: { col: string; sortBy: string; sortDir: string }) {
  if (col !== sortBy) return null
  return sortDir === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
}

function valueOrAlias(lead: LeadItem, canonicalKey: keyof LeadItem, aliasKey: keyof LeadItem): string {
  const canonical = lead[canonicalKey]
  if (typeof canonical === 'string' && canonical.trim()) return canonical
  const alias = lead[aliasKey]
  return typeof alias === 'string' ? alias : ''
}

export default function LeadsTable({
  leads,
  loading,
  selected,
  onSelect,
  onSelectAll,
  onPatch,
  onDelete,
  onDetail,
  sortBy,
  sortDir,
  onSort,
}: Props) {
  const allSelected = leads.length > 0 && leads.every((lead) => selected.has(lead.id))

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1860px] text-[13px]">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="w-10 px-3 py-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onSelectAll}
                  className="accent-white"
                />
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  onClick={() => {
                    if (column.sortable) onSort(column.key)
                  }}
                  className={`select-none px-3 py-3 text-left text-[11px] font-medium uppercase tracking-wider text-nexus-muted ${column.width} ${
                    column.sortable ? 'cursor-pointer transition-colors hover:text-white' : ''
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {column.label}
                    {column.sortable ? <SortIcon col={column.key} sortBy={sortBy} sortDir={sortDir} /> : null}
                  </span>
                </th>
              ))}
              <th className="w-12 px-3 py-3" />
            </tr>
          </thead>

          <tbody className="divide-y divide-white/[0.04]">
            {loading ? (
              <SkeletonTable rows={10} cols={columns.length + 2} />
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 2} className="px-6 py-16 text-center text-[13px] text-nexus-muted">
                  Nenhum lead encontrado
                </td>
              </tr>
            ) : (
              leads.map((lead) => {
                const company = valueOrAlias(lead, 'company_name', 'empresa')
                const niche = valueOrAlias(lead, 'niche', 'nicho')
                const city = valueOrAlias(lead, 'city', 'cidade')
                const country = valueOrAlias(lead, 'country', 'pais')
                const phone = valueOrAlias(lead, 'phone', 'telefone')
                const site = valueOrAlias(lead, 'website', 'site')
                const email = valueOrAlias(lead, 'email', 'email')
                const cleanPhone = formatPhone(phone)

                return (
                  <tr key={lead.id} className="group transition-colors hover:bg-white/[0.02]">
                    <td className="px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={selected.has(lead.id)}
                        onChange={() => onSelect(lead.id)}
                        className="accent-white"
                      />
                    </td>

                    <td className="px-3 py-2.5 align-top">
                      <select
                        value={lead.status}
                        onChange={(event) => onPatch(lead.id, { status: event.target.value })}
                        className="mb-1 block rounded-md border border-white/[0.08] bg-transparent px-2 py-1 text-[11px] font-medium text-zinc-300 focus:border-white/[0.2]"
                      >
                        {statusOptions.map((option) => (
                          <option key={option.value} value={option.value} className="bg-zinc-900">
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <Badge status={lead.status} />
                    </td>

                    <td className="px-3 py-2.5">
                      <button
                        type="button"
                        onClick={() => onDetail(lead.id)}
                        className="max-w-[240px] truncate text-left font-medium text-white transition-colors hover:text-zinc-300"
                        title={company}
                      >
                        {truncate(company || '-', 42)}
                      </button>
                      <p className="mt-0.5 truncate text-[11px] text-nexus-muted">{niche || '-'}</p>
                    </td>

                    <td className="px-3 py-2.5">
                      {phone ? (
                        <a href={`tel:${cleanPhone}`} className="inline-flex items-center gap-1.5 text-zinc-400 transition-colors hover:text-white">
                          <Phone className="h-3 w-3 text-zinc-600" />
                          {phone}
                        </a>
                      ) : (
                        <span className="text-zinc-700">-</span>
                      )}
                    </td>

                    <td className="px-3 py-2.5">
                      {email ? (
                        <a href={`mailto:${email}`} className="inline-flex items-center gap-1 text-[12px] text-zinc-400 transition-colors hover:text-white">
                          <Mail className="h-3 w-3" />
                          {truncate(email, 28)}
                        </a>
                      ) : (
                        <span className="text-zinc-700">-</span>
                      )}
                    </td>

                    <td className="px-3 py-2.5">
                      {site ? (
                        <a
                          href={site}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-[12px] text-zinc-400 transition-colors hover:text-white"
                          title={site}
                        >
                          <Globe className="h-3 w-3" />
                          {truncate(site, 28)}
                        </a>
                      ) : (
                        <span className="text-zinc-700">-</span>
                      )}
                    </td>

                    <td className="px-3 py-2.5">
                      {Number.isFinite(Number(lead.rating)) && lead.rating != null ? (
                        <span className="inline-flex items-center gap-1 text-[12px] text-zinc-300">
                          <Star className="h-3.5 w-3.5 text-amber-400" />
                          {Number(lead.rating).toFixed(1)}
                        </span>
                      ) : (
                        <span className="text-zinc-700">-</span>
                      )}
                    </td>

                    <td className="max-w-[160px] truncate px-3 py-2.5 text-[12px] text-zinc-400" title={city || ''}>
                      {city || '-'}
                      <div className="text-[10px] text-zinc-600">{country || '-'}</div>
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        min={0}
                        defaultValue={lead.ticket_estimado || 0}
                        onBlur={(event) => onPatch(lead.id, { ticket_estimado: Number(event.target.value) || 0 })}
                        className="w-28 rounded-md border border-white/[0.08] bg-transparent px-2 py-1 text-[12px] text-zinc-300 focus:border-white/[0.2]"
                      />
                      <p className="mt-0.5 text-[10px] text-zinc-600">{formatCurrency(lead.ticket_estimado || 0)}</p>
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        defaultValue={lead.chance_fechamento || 0}
                        onBlur={(event) => onPatch(lead.id, { chance_fechamento: Number(event.target.value) || 0 })}
                        className="w-20 rounded-md border border-white/[0.08] bg-transparent px-2 py-1 text-[12px] text-zinc-300 focus:border-white/[0.2]"
                      />
                      <span className="ml-1 text-[12px] text-zinc-600">%</span>
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="datetime-local"
                        defaultValue={toDateTimeLocal(lead.proximo_follow_up)}
                        onBlur={(event) => onPatch(lead.id, { proximo_follow_up: event.target.value || null })}
                        className="w-40 rounded-md border border-white/[0.08] bg-transparent px-2 py-1 text-[12px] text-zinc-300 focus:border-white/[0.2]"
                      />
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="datetime-local"
                        defaultValue={toDateTimeLocal(lead.ultimo_contato)}
                        onBlur={(event) => onPatch(lead.id, { ultimo_contato: event.target.value || null })}
                        className="w-40 rounded-md border border-white/[0.08] bg-transparent px-2 py-1 text-[12px] text-zinc-300 focus:border-white/[0.2]"
                      />
                    </td>

                    <td className="px-3 py-2.5">
                      <textarea
                        defaultValue={lead.observacoes || ''}
                        onBlur={(event) => onPatch(lead.id, { observacoes: event.target.value })}
                        className="h-14 w-52 resize-none rounded-md border border-white/[0.08] bg-transparent px-2 py-1 text-[12px] text-zinc-300 focus:border-white/[0.2]"
                      />
                    </td>

                    <td className="px-3 py-2.5">
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm('Excluir este lead?')) onDelete(lead.id)
                        }}
                        className="text-zinc-700 opacity-0 transition group-hover:opacity-100 hover:text-red-400"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function toDateTimeLocal(value?: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
