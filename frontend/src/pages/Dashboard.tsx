import { useState, useCallback } from 'react'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import Header from '../components/layout/Header'
import StatsCards from '../components/layout/StatsCards'
import LeadsTable from '../components/leads/LeadsTable'
import BulkActions from '../components/leads/BulkActions'
import LeadDetailModal from '../components/leads/LeadDetailModal'
import { useLeads } from '../hooks/useLeads'
import { useToast } from '../components/ui/Toast'
import { api } from '../services/api'

export default function Dashboard() {
  const { leads, stats, countries, total, pages, loading, filters, setFilter, toggleSort, reload } = useLeads()
  const toast = useToast()
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [detail, setDetail] = useState<Record<string, any> | null>(null)
  const [searchInput, setSearchInput] = useState('')

  const toggleSelect = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  const toggleAll = useCallback(() => {
    setSelected((prev) =>
      prev.size === leads.length ? new Set() : new Set(leads.map((l: any) => l._id))
    )
  }, [leads])

  const markOne = async (id: number, status: string) => {
    await api('/api/leads/mark', { method: 'POST', body: JSON.stringify({ ids: [id], status }) })
    toast(`Lead marcado como ${status}`)
    reload()
  }

  const bulkMark = async (status: string) => {
    const ids = [...selected]
    if (!ids.length) return
    await api('/api/leads/mark', { method: 'POST', body: JSON.stringify({ ids, status }) })
    toast(`${ids.length} leads marcados como ${status}`)
    setSelected(new Set())
    reload()
  }

  const deleteOne = async (id: number) => {
    await api('/api/leads/delete', { method: 'POST', body: JSON.stringify({ ids: [id] }) })
    toast('Lead excluído')
    reload()
  }

  const bulkDelete = async () => {
    const ids = [...selected]
    if (!ids.length || !confirm(`Excluir ${ids.length} leads permanentemente?`)) return
    await api('/api/leads/delete', { method: 'POST', body: JSON.stringify({ ids }) })
    toast(`${ids.length} leads excluídos`)
    setSelected(new Set())
    reload()
  }

  const openDetail = async (id: number) => {
    try {
      const lead = await api(`/api/leads/${id}`)
      setDetail(lead)
    } catch {}
  }

  let searchTimer: ReturnType<typeof setTimeout>
  const handleSearch = (val: string) => {
    setSearchInput(val)
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => setFilter('search', val), 400)
  }

  return (
    <>
      <Header title="Dashboard" />
      <main className="p-6 space-y-6">
        <StatsCards stats={stats} onFilter={(s) => setFilter('status', s)} />

        {/* Filters */}
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5">Status</label>
            <select
              value={filters.status}
              onChange={(e) => setFilter('status', e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:border-nexus-accent transition"
            >
              <option value="todos">Todos</option>
              <option value="novo">Novos</option>
              <option value="contatado">Contatados</option>
              <option value="fechado">Fechados</option>
              <option value="ignorado">Ignorados</option>
            </select>
          </div>
          <div>
            <label className="block text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5">País</label>
            <select
              value={filters.pais}
              onChange={(e) => setFilter('pais', e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:border-nexus-accent transition"
            >
              <option value="todos">Todos</option>
              {countries.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-[220px]">
            <label className="block text-[11px] text-zinc-500 uppercase tracking-wider mb-1.5">Buscar</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Nome, telefone, cidade..."
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-4 py-2 text-sm text-zinc-300 placeholder-zinc-600 focus:border-nexus-accent transition"
              />
            </div>
          </div>
        </div>

        {/* Bulk actions + count */}
        <div className="flex items-center justify-between">
          <BulkActions count={selected.size} onMark={bulkMark} onDelete={bulkDelete} />
          <span className="text-xs text-zinc-600">{total} leads</span>
        </div>

        {/* Table */}
        <LeadsTable
          leads={leads}
          loading={loading}
          selected={selected}
          onSelect={toggleSelect}
          onSelectAll={toggleAll}
          onStatusChange={markOne}
          onDelete={deleteOne}
          onDetail={openDetail}
          sortBy={filters.sort_by}
          sortDir={filters.sort_dir}
          onSort={toggleSort}
        />

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => setFilter('page', Math.max(1, filters.page - 1))}
              disabled={filters.page <= 1}
              className="flex items-center gap-1 text-sm text-zinc-400 hover:text-white disabled:text-zinc-700 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft className="w-4 h-4" /> Anterior
            </button>
            <span className="text-sm text-zinc-500">
              {filters.page} / {pages}
            </span>
            <button
              onClick={() => setFilter('page', Math.min(pages, filters.page + 1))}
              disabled={filters.page >= pages}
              className="flex items-center gap-1 text-sm text-zinc-400 hover:text-white disabled:text-zinc-700 disabled:cursor-not-allowed transition"
            >
              Próximo <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </main>

      <LeadDetailModal lead={detail} onClose={() => setDetail(null)} />
    </>
  )
}
