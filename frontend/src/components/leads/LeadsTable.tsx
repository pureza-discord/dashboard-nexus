import { ChevronDown, ChevronUp, Mail, Phone, Trash2 } from 'lucide-react'
import type { LeadItem, LeadStatus } from '../../hooks/useLeads'
import Badge from '../ui/Badge'
import { SkeletonTable } from '../ui/Skeleton'
import { formatCurrency, formatPhone, truncate } from '../../utils/format'

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
  { key: 'cidade', label: 'Cidade', width: 'w-32', sortable: true },
  { key: 'ticket_estimado', label: 'Ticket', width: 'w-34', sortable: true },
  { key: 'chance_fechamento', label: 'Chance', width: 'w-26', sortable: true },
  { key: 'proximo_follow_up', label: 'Follow-up', width: 'w-40', sortable: false },
  { key: 'ultimo_contato', label: 'Último contato', width: 'w-40', sortable: false },
  { key: 'observacoes', label: 'Observações', width: 'w-52', sortable: false },
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
    <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-[#0a0a0a]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1680px] text-[13px]">
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
                  className={`select-none px-3 py-3 text-left text-[11px] font-medium uppercase tracking-[0.12em] text-[#555555] ${column.width} ${
                    column.sortable ? 'cursor-pointer transition hover:text-[#999999]' : ''
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
                <td colSpan={columns.length + 2} className="px-6 py-16 text-center text-[13px] text-[#555555]">
                  Nenhum lead encontrado
                </td>
              </tr>
            ) : (
              leads.map((lead) => {
                const tel = lead.telefone || ''
                const cleanTel = formatPhone(tel)

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
                        onChange={(e) => onPatch(lead.id, { status: e.target.value })}
                        className="mb-1 block rounded border border-white/[0.08] bg-black px-2 py-1 text-[11px] font-medium text-[#cccccc]"
                      >
                        {statusOptions.map((option) => (
                          <option key={option.value} value={option.value} className="bg-black">
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
                        className="max-w-[240px] truncate text-left font-medium text-white transition hover:text-[#cccccc]"
                        title={lead.empresa}
                      >
                        {truncate(lead.empresa || '-', 42)}
                      </button>
                      <p className="mt-1 truncate text-[11px] text-[#555555]">{lead.nicho || '-'}</p>
                    </td>

                    <td className="px-3 py-2.5">
                      {tel ? (
                        <a href={`tel:${cleanTel}`} className="inline-flex items-center gap-1.5 text-[#888888] transition hover:text-white">
                          <Phone className="h-3 w-3 text-[#555555]" />
                          {tel}
                        </a>
                      ) : (
                        <span className="text-[#333333]">-</span>
                      )}
                    </td>

                    <td className="px-3 py-2.5">
                      {lead.email ? (
                        <a href={`mailto:${lead.email}`} className="inline-flex items-center gap-1 text-[12px] text-[#888888] transition hover:text-white">
                          <Mail className="h-3 w-3" />
                          {truncate(lead.email, 28)}
                        </a>
                      ) : (
                        <span className="text-[#333333]">-</span>
                      )}
                    </td>

                    <td className="max-w-[140px] truncate px-3 py-2.5 text-[12px] text-[#888888]" title={lead.cidade || ''}>
                      {lead.cidade || '-'}
                      <div className="text-[10px] text-[#444444]">{lead.pais || '-'}</div>
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        min={0}
                        defaultValue={lead.ticket_estimado || 0}
                        onBlur={(e) => onPatch(lead.id, { ticket_estimado: Number(e.target.value) || 0 })}
                        className="w-28 rounded border border-white/[0.08] bg-black px-2 py-1 text-[12px] text-[#cccccc]"
                      />
                      <p className="mt-1 text-[10px] text-[#555555]">{formatCurrency(lead.ticket_estimado || 0)}</p>
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        defaultValue={lead.chance_fechamento || 0}
                        onBlur={(e) => onPatch(lead.id, { chance_fechamento: Number(e.target.value) || 0 })}
                        className="w-20 rounded border border-white/[0.08] bg-black px-2 py-1 text-[12px] text-[#cccccc]"
                      />
                      <span className="ml-1 text-[12px] text-[#555555]">%</span>
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="datetime-local"
                        defaultValue={toDateTimeLocal(lead.proximo_follow_up)}
                        onBlur={(e) => onPatch(lead.id, { proximo_follow_up: e.target.value || null })}
                        className="w-40 rounded border border-white/[0.08] bg-black px-2 py-1 text-[12px] text-[#cccccc]"
                      />
                    </td>

                    <td className="px-3 py-2.5">
                      <input
                        type="datetime-local"
                        defaultValue={toDateTimeLocal(lead.ultimo_contato)}
                        onBlur={(e) => onPatch(lead.id, { ultimo_contato: e.target.value || null })}
                        className="w-40 rounded border border-white/[0.08] bg-black px-2 py-1 text-[12px] text-[#cccccc]"
                      />
                    </td>

                    <td className="px-3 py-2.5">
                      <textarea
                        defaultValue={lead.observacoes || ''}
                        onBlur={(e) => onPatch(lead.id, { observacoes: e.target.value })}
                        className="h-14 w-52 resize-none rounded border border-white/[0.08] bg-black px-2 py-1 text-[12px] text-[#cccccc]"
                      />
                    </td>

                    <td className="px-3 py-2.5">
                      <button
                        type="button"
                        onClick={() => {
                          if (window.confirm('Excluir este lead?')) onDelete(lead.id)
                        }}
                        className="text-[#333333] opacity-0 transition group-hover:opacity-100 hover:text-nexus-red"
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
