import { Phone, Globe, Mail, MessageCircle, Trash2, ChevronUp, ChevronDown } from 'lucide-react'
import Badge from '../ui/Badge'
import { SkeletonTable } from '../ui/Skeleton'
import { formatPhone, truncate } from '../../utils/format'

interface Lead {
  _id: number
  _status: string
  nome_empresa?: string
  telefone?: string
  email?: string
  site?: string
  cidade?: string
  pais?: string
  observacoes?: string
  instagram?: string
}

interface Props {
  leads: Lead[]
  loading: boolean
  selected: Set<number>
  onSelect: (id: number) => void
  onSelectAll: () => void
  onStatusChange: (id: number, status: string) => void
  onDelete: (id: number) => void
  onDetail: (id: number) => void
  sortBy: string
  sortDir: string
  onSort: (col: string) => void
}

const columns = [
  { key: 'status', label: 'Status', w: 'w-24' },
  { key: 'nome_empresa', label: 'Empresa', w: 'min-w-[180px]' },
  { key: 'telefone', label: 'Telefone', w: 'w-40' },
  { key: 'email', label: 'Email', w: 'w-44' },
  { key: 'site', label: 'Site', w: 'w-36' },
  { key: 'cidade', label: 'Cidade', w: 'w-32' },
  { key: 'pais', label: 'País', w: 'w-24' },
  { key: 'observacoes', label: 'Obs', w: 'w-32' },
]

function SortIcon({ col, sortBy, sortDir }: { col: string; sortBy: string; sortDir: string }) {
  if (col !== sortBy) return null
  return sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
}

export default function LeadsTable({
  leads, loading, selected, onSelect, onSelectAll, onStatusChange, onDelete, onDetail, sortBy, sortDir, onSort,
}: Props) {
  const allSelected = leads.length > 0 && leads.every((l) => selected.has(l._id))

  return (
    <div className="bg-nexus-card border border-white/[0.06] rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/[0.06]">
              <th className="px-3 py-3 w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={onSelectAll}
                  className="accent-blue-500 rounded"
                />
              </th>
              {columns.map((c) => (
                <th
                  key={c.key}
                  onClick={() => onSort(c.key)}
                  className={`px-3 py-3 text-left text-[11px] font-medium text-zinc-500 uppercase tracking-wider cursor-pointer hover:text-zinc-300 transition select-none ${c.w}`}
                >
                  <span className="flex items-center gap-1">
                    {c.label}
                    <SortIcon col={c.key} sortBy={sortBy} sortDir={sortDir} />
                  </span>
                </th>
              ))}
              <th className="px-3 py-3 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {loading ? (
              <SkeletonTable rows={10} cols={columns.length + 2} />
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 2} className="px-6 py-16 text-center text-zinc-600">
                  Nenhum lead encontrado
                </td>
              </tr>
            ) : (
              leads.map((l) => {
                const tel = l.telefone || ''
                const cleanTel = formatPhone(tel)
                const waUrl = cleanTel ? `https://wa.me/${cleanTel.replace('+', '')}` : ''
                const siteHost = l.site ? (() => { try { return new URL(l.site).hostname.replace('www.', '') } catch { return l.site } })() : ''

                return (
                  <tr key={l._id} className="group hover:bg-white/[0.02] transition">
                    <td className="px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={selected.has(l._id)}
                        onChange={() => onSelect(l._id)}
                        className="accent-blue-500 rounded"
                      />
                    </td>
                    <td className="px-3 py-2.5">
                      <select
                        value={l._status}
                        onChange={(e) => onStatusChange(l._id, e.target.value)}
                        className="bg-transparent border-0 text-[11px] font-semibold cursor-pointer focus:ring-0 p-0"
                      >
                        {['novo', 'contatado', 'fechado', 'ignorado'].map((s) => (
                          <option key={s} value={s} className="bg-zinc-900">{s}</option>
                        ))}
                      </select>
                      <Badge status={l._status} />
                    </td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => onDetail(l._id)}
                        className="font-medium text-white hover:text-nexus-accent transition text-left truncate max-w-[200px] block"
                        title={l.nome_empresa}
                      >
                        {truncate(l.nome_empresa || '—', 35)}
                      </button>
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {tel ? (
                        <span className="flex items-center gap-1.5">
                          <a href={`tel:${cleanTel}`} className="text-zinc-300 hover:text-white transition flex items-center gap-1">
                            <Phone className="w-3 h-3 text-zinc-500" />
                            {tel}
                          </a>
                          {waUrl && (
                            <a href={waUrl} target="_blank" rel="noreferrer" className="text-emerald-500 hover:text-emerald-400" title="WhatsApp">
                              <MessageCircle className="w-3.5 h-3.5" />
                            </a>
                          )}
                        </span>
                      ) : <span className="text-zinc-700">—</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {l.email ? (
                        <a href={`mailto:${l.email}`} className="text-zinc-400 hover:text-white transition flex items-center gap-1 text-xs">
                          <Mail className="w-3 h-3" />{truncate(l.email, 25)}
                        </a>
                      ) : <span className="text-zinc-700">—</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {l.site ? (
                        <a href={l.site} target="_blank" rel="noreferrer" className="text-nexus-accent hover:text-blue-400 transition flex items-center gap-1 text-xs">
                          <Globe className="w-3 h-3" />{truncate(siteHost, 20)}
                        </a>
                      ) : <span className="text-zinc-700">—</span>}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-zinc-500 truncate max-w-[120px]" title={l.cidade}>{l.cidade || '—'}</td>
                    <td className="px-3 py-2.5">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-500">{l.pais || ''}</span>
                    </td>
                    <td className="px-3 py-2.5 text-[11px] text-zinc-600 truncate max-w-[120px]" title={l.observacoes}>{truncate(l.observacoes || '', 20)}</td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => { if (confirm('Excluir este lead?')) onDelete(l._id) }}
                        className="text-zinc-700 hover:text-red-400 opacity-0 group-hover:opacity-100 transition"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
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
