import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  Download,
  RefreshCcw,
  Search,
} from 'lucide-react'
import LeadsTable from '../components/leads/LeadsTable'
import BulkActions from '../components/leads/BulkActions'
import LeadDetailModal from '../components/leads/LeadDetailModal'
import { useLeads } from '../hooks/useLeads'
import { useToast } from '../components/ui/Toast'
import { api, getToken } from '../services/api'
import { useSearchParams } from 'react-router-dom'

const RAW_API_BASE_URL = String(import.meta.env.VITE_API_BASE_URL || '').trim()
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '')

export default function Leads() {
  const {
    leads,
    countries,
    total,
    pages,
    loading,
    error,
    filters,
    setFilter,
    resetFilters,
    toggleSort,
    reload,
  } = useLeads()
  const toast = useToast()
  const [searchParams] = useSearchParams()

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [searchInput, setSearchInput] = useState('')
  const [busyAction, setBusyAction] = useState(false)
  const searchTimerRef = useRef<number | null>(null)

  useEffect(() => {
    const statusParam = searchParams.get('status')
    if (statusParam && statusParam !== filters.status) {
      setFilter('status', statusParam)
    }
  }, [searchParams, filters.status, setFilter])

  useEffect(() => {
    setSearchInput(filters.search)
  }, [filters.search])

  useEffect(() => {
    setSelected((prev) => {
      const validIds = new Set(leads.map((lead) => lead.id))
      return new Set([...prev].filter((id) => validIds.has(id)))
    })
  }, [leads])

  useEffect(() => {
    if (searchTimerRef.current !== null) window.clearTimeout(searchTimerRef.current)
    searchTimerRef.current = window.setTimeout(() => {
      setFilter('search', searchInput)
    }, 350)
    return () => {
      if (searchTimerRef.current !== null) window.clearTimeout(searchTimerRef.current)
    }
  }, [searchInput, setFilter])

  const patchLead = async (id: string, payload: Record<string, unknown>) => {
    try {
      await api(`/api/leads/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
      await reload()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Falha ao atualizar lead', 'error')
    }
  }

  const bulkMark = async (status: string) => {
    const leadIds = [...selected]
    if (!leadIds.length) return
    try {
      setBusyAction(true)
      await api('/api/leads/bulk/status', {
        method: 'POST',
        body: JSON.stringify({ lead_ids: leadIds, status }),
      })
      toast(`${leadIds.length} leads atualizados`, 'ok')
      setSelected(new Set())
      await reload()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Falha ao atualizar leads', 'error')
    } finally {
      setBusyAction(false)
    }
  }

  const deleteOne = async (id: string) => {
    try {
      setBusyAction(true)
      await api(`/api/leads/${id}`, { method: 'DELETE' })
      toast('Lead removido', 'ok')
      await reload()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Falha ao remover lead', 'error')
    } finally {
      setBusyAction(false)
    }
  }

  const bulkDelete = async () => {
    const leadIds = [...selected]
    if (!leadIds.length) return
    if (!window.confirm(`Excluir ${leadIds.length} leads permanentemente?`)) return
    try {
      setBusyAction(true)
      await Promise.all(leadIds.map((id) => api(`/api/leads/${id}`, { method: 'DELETE' })))
      toast(`${leadIds.length} leads removidos`, 'ok')
      setSelected(new Set())
      await reload()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Falha ao excluir leads', 'error')
    } finally {
      setBusyAction(false)
    }
  }

  const openDetail = async (id: string) => {
    try {
      const lead = await api<Record<string, unknown>>(`/api/leads/${id}`)
      setDetail(lead)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Falha ao carregar detalhes', 'error')
    }
  }

  const exportCsv = async () => {
    try {
      const token = getToken()
      const exportUrl = API_BASE_URL ? `${API_BASE_URL}/api/leads/export/csv` : '/api/leads/export/csv'
      const response = await fetch(exportUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      })
      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || 'Falha ao exportar CSV')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'leads.csv'
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      toast('CSV exportado com sucesso', 'ok')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Falha ao exportar CSV', 'error')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">Leads</h1>
          <p className="mt-1 text-[13px] text-nexus-muted">{total} leads encontrados</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => { void reload() }}
            className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] px-3 py-2 text-[13px] font-medium text-nexus-muted transition-colors hover:border-white/[0.15] hover:text-white"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading || busyAction ? 'animate-spin' : ''}`} />
            Atualizar
          </button>
          <button
            type="button"
            onClick={() => { void exportCsv() }}
            className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] px-3 py-2 text-[13px] font-medium text-nexus-muted transition-colors hover:border-white/[0.15] hover:text-white"
          >
            <Download className="h-3.5 w-3.5" />
            CSV
          </button>
        </div>
      </div>

      <div className="card p-4 md:p-5">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[12px] font-medium text-nexus-muted">Filtros</span>
          <button
            type="button"
            onClick={() => {
              resetFilters()
              setSearchInput('')
            }}
            className="text-[12px] text-nexus-muted transition-colors hover:text-white"
          >
            Limpar
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Field label="Status">
            <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)} className="input-base">
              <option value="todos">Todos</option>
              <option value="novos">Novos</option>
              <option value="contatados">Contatados</option>
              <option value="proposta">Proposta</option>
              <option value="fechados">Fechados</option>
              <option value="perdidos">Perdidos</option>
            </select>
          </Field>
          <Field label="Pais">
            <select value={filters.pais} onChange={(e) => setFilter('pais', e.target.value)} className="input-base">
              <option value="">Todos</option>
              {countries.map((country) => (
                <option key={country} value={country}>{country}</option>
              ))}
            </select>
          </Field>
          <Field label="Cidade">
            <input value={filters.cidade} onChange={(e) => setFilter('cidade', e.target.value)} className="input-base" placeholder="Cidade" />
          </Field>
          <Field label="Nicho">
            <input value={filters.nicho} onChange={(e) => setFilter('nicho', e.target.value)} className="input-base" placeholder="Nicho" />
          </Field>
          <Field label="Por pagina">
            <select value={filters.per_page} onChange={(e) => setFilter('per_page', Number(e.target.value))} className="input-base">
              {[25, 50, 100, 200].map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </Field>
        </div>

        <div className="mt-3">
          <label className="block">
            <span className="mb-1.5 block text-[12px] font-medium text-nexus-muted">Busca</span>
            <span className="flex items-center gap-2 rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 py-2">
              <Search className="h-4 w-4 flex-shrink-0 text-zinc-600" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-full bg-transparent text-[13px] text-white placeholder-zinc-600 focus:outline-none"
                placeholder="Empresa, email, telefone, cidade..."
              />
            </span>
          </label>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-[13px] text-red-400">
          {error}
        </div>
      ) : null}

      <div className="space-y-3">
        <BulkActions count={selected.size} onMark={bulkMark} onDelete={bulkDelete} />

        <LeadsTable
          leads={leads}
          loading={loading}
          selected={selected}
          onSelect={(id) => {
            setSelected((prev) => {
              const next = new Set(prev)
              if (next.has(id)) next.delete(id)
              else next.add(id)
              return next
            })
          }}
          onSelectAll={() => {
            setSelected((prev) => (prev.size === leads.length ? new Set() : new Set(leads.map((lead) => lead.id))))
          }}
          onPatch={patchLead}
          onDelete={deleteOne}
          onDetail={openDetail}
          sortBy={filters.sort_by}
          sortDir={filters.sort_dir}
          onSort={toggleSort}
        />

        {pages > 1 ? (
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => setFilter('page', Math.max(1, filters.page - 1))}
              disabled={filters.page <= 1}
              className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] px-3 py-1.5 text-[13px] text-nexus-muted transition-colors hover:border-white/[0.15] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Anterior
            </button>
            <span className="text-[13px] tabular-nums text-nexus-muted">
              {filters.page} / {pages}
            </span>
            <button
              type="button"
              onClick={() => setFilter('page', Math.min(pages, filters.page + 1))}
              disabled={filters.page >= pages}
              className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] px-3 py-1.5 text-[13px] text-nexus-muted transition-colors hover:border-white/[0.15] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            >
              Proximo
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </div>

      <LeadDetailModal lead={detail} onClose={() => setDetail(null)} />
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-medium text-nexus-muted">{label}</span>
      {children}
    </label>
  )
}
