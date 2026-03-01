"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, Loader2, Plus, RefreshCw } from "lucide-react";

import { LeadTable } from "@/components/LeadTable";
import { MetricsCards } from "@/components/MetricsCards";
import { NexusAIChat } from "@/components/NexusAIChat";
import { PixPaymentModal } from "@/components/PixPaymentModal";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type LeadStatus = "novos" | "contatados" | "proposta" | "fechados" | "perdidos";

interface Lead {
  id: string;
  status: LeadStatus;
  empresa: string;
  telefone: string | null;
  email: string | null;
  cidade: string | null;
  pais: string | null;
  nicho: string | null;
  chance_fechamento: number;
  proximo_follow_up: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface LeadsResponse {
  leads: Lead[];
  total: number;
}

interface PipelineItem {
  stage: LeadStatus;
  label: string;
  count: number;
}

interface ConversionByCity {
  cidade: string;
  total: number;
  closed: number;
  conversion_rate: number;
}

interface ConversionByNiche {
  nicho: string;
  total: number;
  closed: number;
  conversion_rate: number;
}

interface RevenueByMonth {
  month: string;
  revenue: number;
}

interface AnalyticsOverview {
  leads_this_month: number;
  total_leads: number;
  conversion_rate: number;
  pipeline: PipelineItem[];
  conversion_by_city: ConversionByCity[];
  conversion_by_niche: ConversionByNiche[];
  revenue_by_month: RevenueByMonth[];
}

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/buscas", label: "Minhas Buscas" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/analises", label: "Analises" },
  { href: "/configuracoes", label: "Configuracoes" },
];

function monthKey(date: Date): string {
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${date.getUTCFullYear()}-${month}`;
}

function monthLabel(key: string): string {
  const [year, month] = key.split("-");
  return `${month}/${year.slice(-2)}`;
}

function parseErrorMessage(payload: unknown): string {
  if (!payload) return "Falha na requisicao";
  if (typeof payload === "string") return payload;
  if (typeof payload === "object" && payload !== null) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    const message = (payload as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return "Falha na requisicao";
}

async function apiGet<T>(path: string): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? window.localStorage.getItem("nexus_token") || ""
      : "";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => "");

  if (!response.ok) {
    throw new Error(parseErrorMessage(payload));
  }

  return payload as T;
}

function buildLeadsEvolution(leads: Lead[]): Array<{ month: string; leads: number }> {
  // Regra de produto: o grafico inicia em fevereiro de 2026.
  const start = new Date(Date.UTC(2026, 1, 1, 0, 0, 0, 0));
  const current = new Date();
  const currentMonthStart = new Date(
    Date.UTC(current.getUTCFullYear(), current.getUTCMonth(), 1, 0, 0, 0, 0),
  );

  const counts = new Map<string, number>();
  for (const lead of leads) {
    if (!lead.created_at) continue;
    const createdAt = new Date(lead.created_at);
    if (Number.isNaN(createdAt.getTime()) || createdAt < start) continue;

    const key = monthKey(
      new Date(
        Date.UTC(createdAt.getUTCFullYear(), createdAt.getUTCMonth(), 1, 0, 0, 0, 0),
      ),
    );
    counts.set(key, (counts.get(key) || 0) + 1);
  }

  const timeline: Array<{ month: string; leads: number }> = [];
  const cursor = new Date(start);
  while (cursor <= currentMonthStart) {
    const key = monthKey(cursor);
    timeline.push({
      month: monthLabel(key),
      leads: counts.get(key) || 0,
    });
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }

  return timeline;
}

export default function DashboardPage() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pixModalOpen, setPixModalOpen] = useState(false);

  const loadDashboard = useCallback(async () => {
    setError(null);
    setRefreshing(true);

    try {
      const [overviewResponse, leadsResponse] = await Promise.all([
        apiGet<AnalyticsOverview>("/api/analytics/overview"),
        apiGet<LeadsResponse>("/api/leads?per_page=200&sort_by=created_at&sort_dir=desc"),
      ]);

      setOverview(overviewResponse);
      setLeads(leadsResponse.leads || []);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Nao foi possivel carregar o dashboard";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const pipeline = useMemo(
    () =>
      overview?.pipeline.reduce<Record<LeadStatus, number>>(
        (acc, item) => {
          acc[item.stage] = item.count || 0;
          return acc;
        },
        {
          novos: 0,
          contatados: 0,
          proposta: 0,
          fechados: 0,
          perdidos: 0,
        },
      ) || {
        novos: 0,
        contatados: 0,
        proposta: 0,
        fechados: 0,
        perdidos: 0,
      },
    [overview],
  );

  const evolutionSeries = useMemo(() => buildLeadsEvolution(leads), [leads]);
  const cityConversion = useMemo(
    () => (overview?.conversion_by_city || []).slice(0, 8),
    [overview],
  );
  const nicheConversion = useMemo(
    () => (overview?.conversion_by_niche || []).slice(0, 8),
    [overview],
  );

  const hasClosedDeals = pipeline.fechados > 0;
  const revenueSeries = useMemo(
    () =>
      (overview?.revenue_by_month || [])
        .filter((item) => item.revenue > 0)
        .map((item) => ({
          month: item.month,
          revenue: Number(item.revenue || 0),
        })),
    [overview],
  );

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#0A0F1C] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_10%_10%,rgba(0,245,255,0.12),transparent_35%),radial-gradient(circle_at_85%_20%,rgba(124,58,237,0.16),transparent_40%)]" />

      <div className="relative mx-auto grid min-h-screen max-w-[1720px] grid-cols-1 gap-4 p-4 xl:grid-cols-[220px_1fr_380px]">
        <aside className="rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur-xl">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#00F5FF] to-[#7C3AED] text-lg font-black text-[#0A0F1C]">
              N
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Nexus Leads</p>
              <p className="text-xs text-slate-300">SaaS B2B</p>
            </div>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-xl px-3 py-2 text-sm transition ${
                  item.href === "/dashboard"
                    ? "bg-white/10 text-white"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>

        <section className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-white">
                Dashboard
              </h1>
              <p className="text-sm text-slate-300">
                Operacao de leads com dados reais por conta.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                className="border-white/20 bg-transparent text-slate-100 hover:bg-white/10"
                onClick={() => void loadDashboard()}
                disabled={refreshing}
              >
                {refreshing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Atualizar
              </Button>

              <Button
                variant="outline"
                className="border-[#7C3AED]/50 bg-[#7C3AED]/15 text-[#d9c7ff] hover:bg-[#7C3AED]/25"
                onClick={() => setPixModalOpen(true)}
              >
                Comprar Creditos
              </Button>

              <Button
                className="bg-gradient-to-r from-[#00F5FF] to-[#7C3AED] text-[#0A0F1C] hover:opacity-90"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent("nexus:new-search"));
                }}
              >
                <Plus className="mr-2 h-4 w-4" />
                Nova Busca
              </Button>
            </div>
          </header>

          {error ? (
            <div className="rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                <span>{error}</span>
              </div>
            </div>
          ) : null}

          <MetricsCards
            loading={loading}
            leadsThisMonth={overview?.leads_this_month || 0}
            novos={pipeline.novos}
            contatados={pipeline.contatados}
            proposta={pipeline.proposta}
            fechados={pipeline.fechados}
            perdidos={pipeline.perdidos}
          />

          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1.4fr_1fr]">
            <Card className="border-white/10 bg-white/5 text-slate-100">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Evolucao de Leads</CardTitle>
                <CardDescription className="text-slate-300">
                  Serie mensal real iniciando em fev/2026.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={evolutionSeries}>
                    <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: "#cbd5e1", fontSize: 12 }}
                      axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fill: "#cbd5e1", fontSize: 12 }}
                      axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid rgba(255,255,255,0.12)",
                        borderRadius: 12,
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="leads"
                      stroke="#00F5FF"
                      strokeWidth={3}
                      dot={{ r: 3, fill: "#00F5FF" }}
                      activeDot={{ r: 5, fill: "#00F5FF" }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 gap-4">
              <Card className="border-white/10 bg-white/5 text-slate-100">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Conversao por Cidade</CardTitle>
                  <CardDescription className="text-slate-300">
                    Taxa real de fechamento por cidade.
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={cityConversion}>
                      <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                      <XAxis
                        dataKey="cidade"
                        tick={{ fill: "#cbd5e1", fontSize: 11 }}
                        axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: "#cbd5e1", fontSize: 11 }}
                        axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(value: number) => [`${value}%`, "Conversao"]}
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid rgba(255,255,255,0.12)",
                          borderRadius: 12,
                        }}
                      />
                      <Bar
                        dataKey="conversion_rate"
                        fill="#7C3AED"
                        radius={[8, 8, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card className="border-white/10 bg-white/5 text-slate-100">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Conversao por Nicho</CardTitle>
                  <CardDescription className="text-slate-300">
                    Segmentos com melhor eficiencia comercial.
                  </CardDescription>
                </CardHeader>
                <CardContent className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={nicheConversion}>
                      <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                      <XAxis
                        dataKey="nicho"
                        tick={{ fill: "#cbd5e1", fontSize: 11 }}
                        axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: "#cbd5e1", fontSize: 11 }}
                        axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(value: number) => [`${value}%`, "Conversao"]}
                        contentStyle={{
                          background: "#0f172a",
                          border: "1px solid rgba(255,255,255,0.12)",
                          borderRadius: 12,
                        }}
                      />
                      <Bar
                        dataKey="conversion_rate"
                        fill="#00F5FF"
                        radius={[8, 8, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>
          </div>

          {hasClosedDeals && revenueSeries.length > 0 ? (
            <Card className="border-white/10 bg-white/5 text-slate-100">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Receita por Mes</CardTitle>
                <CardDescription className="text-slate-300">
                  Exibida apenas quando existem contratos fechados.
                </CardDescription>
              </CardHeader>
              <CardContent className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={revenueSeries}>
                    <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: "#cbd5e1", fontSize: 11 }}
                      axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: "#cbd5e1", fontSize: 11 }}
                      axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(value: number) => [
                        `R$ ${Number(value || 0).toLocaleString("pt-BR")}`,
                        "Receita",
                      ]}
                      contentStyle={{
                        background: "#0f172a",
                        border: "1px solid rgba(255,255,255,0.12)",
                        borderRadius: 12,
                      }}
                    />
                    <Bar dataKey="revenue" fill="#22c55e" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          ) : null}

          <LeadTable
            leads={leads}
            loading={loading}
            onLeadUpdated={() => {
              void loadDashboard();
            }}
          />
        </section>

        <aside className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-xl">
          <NexusAIChat
            title="Nexus Scraper"
            subtitle="IA operacional para scraping e inteligencia comercial"
            onTaskCompleted={() => {
              void loadDashboard();
            }}
          />
        </aside>
      </div>

      <PixPaymentModal
        open={pixModalOpen}
        onOpenChange={setPixModalOpen}
        pixPhone="87981544764"
        onPaymentConfirmed={() => {
          setPixModalOpen(false);
          void loadDashboard();
        }}
      />
    </main>
  );
}
