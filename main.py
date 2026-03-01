import argparse
import asyncio
from datetime import date
from pathlib import Path

import questionary
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from database import Database
from google_maps_scraper import GoogleMapsScraper
from natural_parser import parse_natural_query
from procura_servico import ProcuraServicoScraper
from proxy_manager import ProxyManager
from runtime_paths import resolve_db_path
from utils import (
    COLUMNS,
    build_output_stats,
    dedupe_leads_local,
    normalize_leads,
    save_csv,
    save_json,
)
from website_enricher import WebsiteEnricher


console = Console()
PAISES_TODOS = ["Brasil", "Portugal", "Estados Unidos", "Canadá", "Austrália"]
PROJECT_ROOT = Path(__file__).resolve().parent


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in {"false", "0", "no", "nao"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Leads Scraper Premium 2026")
    sub = parser.add_subparsers(dest="cmd")

    # --- Comando: buscar (default) ---
    buscar = sub.add_parser("buscar", help="Buscar novos leads")
    buscar.add_argument("--modo", default="wizard", choices=["wizard", "natural", "config"])
    buscar.add_argument("--texto", help="Frase em linguagem natural para busca.")
    buscar.add_argument("--config", default="config.yaml")
    buscar.add_argument("--headless", default="true")
    buscar.add_argument("--slowmo", default="0")
    buscar.add_argument("--debug", action="store_true")

    # --- Comando: marcar ---
    marcar = sub.add_parser("marcar", help="Marcar lead como contatado/fechado/ignorado")
    marcar.add_argument("--id", type=int, help="ID do lead")
    marcar.add_argument("--nome", help="Busca parcial pelo nome")
    marcar.add_argument("--status", required=True, choices=["contatado", "fechado", "ignorado", "novo"])
    marcar.add_argument("--config", default="config.yaml")

    # --- Comando: listar ---
    listar = sub.add_parser("listar", help="Listar leads do banco")
    listar.add_argument("--status", default=None, help="Filtrar por status (novo/contatado/fechado/ignorado)")
    listar.add_argument("--config", default="config.yaml")

    # --- Comando: exportar ---
    exportar = sub.add_parser("exportar", help="Exportar CSV filtrado por status")
    exportar.add_argument("--status", default="novo", help="Status a exportar (default: novo)")
    exportar.add_argument("--config", default="config.yaml")

    # --- Comando: resumo ---
    sub.add_parser("resumo", help="Mostra contagem por status")

    # Suporte ao modo antigo (sem subcomando)
    parser.add_argument("--modo", default="wizard", choices=["wizard", "natural", "config"])
    parser.add_argument("--texto", default=None)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--headless", default="true")
    parser.add_argument("--slowmo", default="0")
    parser.add_argument("--debug", action="store_true")

    return parser.parse_args()


def _wizard_inputs() -> list[dict]:
    consultas: list[dict] = []

    while True:
        console.print(Panel.fit("[bold]Modo Wizard[/bold] - vamos configurar sua busca!", border_style="green"))

        pais = questionary.select(
            "Qual pais?",
            choices=["Brasil", "Portugal", "Estados Unidos", "Canadá", "Austrália", "Todos"],
        ).ask()

        nicho = questionary.text(
            "Qual nicho? (ex: Clinica estetica, Advogado, Imobiliaria)"
        ).ask()
        nicho = (nicho or "").strip()

        cidade = questionary.text(
            "Qual cidade/estado? (ex: Recife, Vitoria-ES, Lisboa) [opcional]"
        ).ask()
        cidade = (cidade or "").strip() or None

        limite = questionary.text("Quantas empresas/leads? (max 500)").ask()
        try:
            limite_int = max(1, min(int(limite), 500))
        except ValueError:
            limite_int = 50

        procura_servico = questionary.confirm("Ativar busca de quem PROCURA servicos? (s/n)").ask()

        consultas.append({
            "pais": pais,
            "nicho": nicho,
            "cidade": cidade,
            "limite": limite_int,
            "procura_servico": bool(procura_servico),
        })

        if not questionary.confirm("Buscar mais algum nicho/pais?").ask():
            break

    return consultas


def _load_config(path: str) -> dict:
    target = Path(path)
    if not target.is_absolute():
        cwd_target = Path.cwd() / target
        project_target = PROJECT_ROOT / target
        if cwd_target.exists():
            target = cwd_target
        else:
            target = project_target

    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_db_path(config: dict) -> str:
    config_raw = str(config.get("database", {}).get("path", "")).strip() or None
    db_path, _source = resolve_db_path(config_db_path=config_raw)
    return db_path


def _build_queries_from_config(config: dict) -> list[dict]:
    consultas = config.get("queries", [])
    return consultas if isinstance(consultas, list) else []


def _build_queries_from_natural(texto: str) -> list[dict]:
    return [parse_natural_query(texto)]


def _split_terms(nicho: str) -> list[str]:
    parts = [p.strip() for p in nicho.replace("/", ",").split(",")]
    return [p for p in parts if p]


def _get_concurrency(config: dict) -> int:
    return int(config.get("performance", {}).get("concurrency", 3))


async def _run_single_query(
    query: dict,
    maps_scraper: GoogleMapsScraper,
    procura_scraper: ProcuraServicoScraper,
    enricher: WebsiteEnricher,
    db: Database,
) -> list[dict]:
    pais = query.get("pais", "Brasil")
    nicho = query.get("nicho", "Negocios locais")
    cidade = query.get("cidade")
    limite = int(query.get("limite", 50))
    procura_servico = bool(query.get("procura_servico", False))

    termos_busca = query.get("termos_busca") or _split_terms(nicho)
    leads: list[dict] = []
    paises = PAISES_TODOS if pais == "Todos" else [pais]

    for pais_atual in paises:
        for termo in termos_busca:
            console.print(
                f"Google Maps: [bold]{termo}[/bold] | {pais_atual} | {cidade or 'sem cidade'} | limite {limite}"
            )
            try:
                leads_maps = await maps_scraper.search_leads(
                    pais=pais_atual, nicho=termo, cidade=cidade, limite=limite,
                    geo=query.get("geo"), raio_km=query.get("raio_km"),
                )
                leads.extend(leads_maps)
            except Exception as e:
                console.print(f"ERRO GoogleMaps: {type(e).__name__}: {e}")
                continue

        if procura_servico:
            console.print("[bold yellow]Procura-servico:[/bold yellow] Buscando quem procura servicos digitais...")
            try:
                leads_procura = await procura_scraper.search_leads(
                    pais=pais_atual, nicho=nicho, cidade=cidade, limite=limite,
                )
                leads.extend(leads_procura)
            except Exception as e:
                console.print(f"ERRO ProcuraServico: {type(e).__name__}: {e}")

    console.print(f"Total bruto: {len(leads)}")
    leads = normalize_leads(leads)
    leads = dedupe_leads_local(leads)

    leads = db.filter_new_leads(leads)
    if not leads:
        console.print("[dim]Nenhum lead novo (todos ja existem no banco)[/dim]")
        return []

    console.print(f"Novos leads para enriquecer: {len(leads)}")
    leads = await enricher.enrich_leads(leads)
    db.upsert_leads(leads)

    return leads


async def _run_all(consultas, config, headless, slowmo_ms):
    proxy_manager = ProxyManager()
    concurrency = _get_concurrency(config)

    maps_scraper = GoogleMapsScraper(
        headless=headless, slowmo_ms=slowmo_ms, proxy_manager=proxy_manager
    )
    procura_scraper = ProcuraServicoScraper(
        headless=headless, slowmo_ms=slowmo_ms, proxy_manager=proxy_manager, concurrency=concurrency
    )
    enricher = WebsiteEnricher(
        headless=headless, slowmo_ms=slowmo_ms, proxy_manager=proxy_manager, concurrency=concurrency
    )

    db_path = _resolve_db_path(config)
    db = Database(db_path)

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _guarded(q):
        async with sem:
            return await _run_single_query(q, maps_scraper, procura_scraper, enricher, db)

    tasks = [asyncio.create_task(_guarded(q)) for q in consultas]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    leads: list[dict] = []
    for item in results:
        if isinstance(item, Exception):
            console.print(f"[red]Erro em query: {item}[/red]")
            continue
        leads.extend(item)

    return leads


def _export_outputs(leads, config):
    output_dir = Path(config.get("output", {}).get("dir", "output"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    base = f"leads_{date.today().isoformat()}"
    csv_path = output_dir / f"{base}.csv"
    json_path = output_dir / f"{base}.json"

    save_csv(leads, str(csv_path))
    save_json(leads, str(json_path))

    sheets_cfg = config.get("google_sheets", {})
    if sheets_cfg.get("enabled"):
        from utils import export_to_gsheets
        export_to_gsheets(
            leads,
            sheet_id=sheets_cfg.get("sheet_id"),
            credentials_path=sheets_cfg.get("credentials_path"),
            worksheet_name=sheets_cfg.get("worksheet", "Leads"),
            columns=COLUMNS,
        )

    return {"csv": str(csv_path), "json": str(json_path)}


def _print_summary(leads):
    stats = build_output_stats(leads)
    table = Table(title="Resumo Final")
    table.add_column("Metrica")
    table.add_column("Total")
    for label, value in stats.items():
        table.add_row(label, str(value))
    console.print(table)


# ======================================================================
# Subcommands
# ======================================================================

def _cmd_buscar(args):
    if args.debug:
        headless, slowmo_ms = False, 250
    else:
        headless = _parse_bool(args.headless)
        slowmo_ms = int(args.slowmo or 0)

    config = _load_config(args.config)

    modo = getattr(args, "modo", "wizard")
    if modo == "config":
        consultas = _build_queries_from_config(config)
    elif modo == "natural":
        texto = getattr(args, "texto", None)
        if not texto:
            console.print("Modo natural precisa de --texto.")
            return
        consultas = _build_queries_from_natural(texto)
    else:
        consultas = _wizard_inputs()

    if not consultas:
        console.print("Nenhuma consulta.")
        return

    leads = asyncio.run(_run_all(consultas, config, headless=headless, slowmo_ms=slowmo_ms))
    outputs = _export_outputs(leads, config)
    _print_summary(leads)
    console.print(f"[bold green]Concluido! {len(leads)} leads salvos em {outputs['csv']}[/bold green]")


def _cmd_marcar(args):
    config = _load_config(args.config)
    db = Database(_resolve_db_path(config))

    if args.id:
        ok = db.mark(args.id, args.status)
        if ok:
            console.print(f"Lead #{args.id} marcado como [bold]{args.status}[/bold]")
        else:
            console.print(f"Lead #{args.id} nao encontrado")
    elif args.nome:
        n = db.mark_by_name(args.nome, args.status)
        console.print(f"{n} lead(s) com '{args.nome}' marcados como [bold]{args.status}[/bold]")
    else:
        console.print("Informe --id ou --nome")


def _cmd_listar(args):
    config = _load_config(getattr(args, "config", "config.yaml"))
    db = Database(_resolve_db_path(config))

    leads = db.get_leads(status=args.status)
    if not leads:
        console.print("Nenhum lead encontrado.")
        return

    table = Table(title=f"Leads ({args.status or 'todos'})")
    table.add_column("ID", style="dim")
    table.add_column("Status")
    table.add_column("Nome")
    table.add_column("Telefone")
    table.add_column("Cidade")
    table.add_column("Obs")

    for l in leads[:100]:
        status_style = {"novo": "green", "contatado": "yellow", "fechado": "blue", "ignorado": "dim"}.get(l["_status"], "")
        table.add_row(
            str(l["_id"]),
            f"[{status_style}]{l['_status']}[/{status_style}]",
            (l.get("nome_empresa") or "")[:45],
            l.get("telefone", ""),
            l.get("cidade", ""),
            (l.get("observacoes") or "")[:30],
        )

    console.print(table)
    if len(leads) > 100:
        console.print(f"[dim]... e mais {len(leads) - 100} leads[/dim]")


def _cmd_exportar(args):
    config = _load_config(args.config)
    db = Database(_resolve_db_path(config))

    leads = db.get_leads(status=args.status)
    if not leads:
        console.print(f"Nenhum lead com status '{args.status}'")
        return

    output_dir = Path(config.get("output", {}).get("dir", "output"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"leads_{args.status}_{date.today().isoformat()}.csv"

    save_csv(leads, str(path))
    console.print(f"[bold green]{len(leads)} leads exportados em {path}[/bold green]")


def _cmd_resumo(_args):
    config = _load_config("config.yaml")
    db = Database(_resolve_db_path(config))

    counts = db.count_by_status()
    total = sum(counts.values())

    table = Table(title="Resumo do Banco de Leads")
    table.add_column("Status")
    table.add_column("Quantidade")
    table.add_column("%")

    for status, count in sorted(counts.items()):
        pct = f"{count / max(total, 1) * 100:.1f}%"
        table.add_row(status, str(count), pct)

    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "100%")
    console.print(table)


# ======================================================================
# Main
# ======================================================================

def main():
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    args = _parse_args()

    console.print(Panel.fit("Leads Scraper Premium 2026", border_style="cyan"))

    cmd = getattr(args, "cmd", None)

    if cmd == "marcar":
        _cmd_marcar(args)
    elif cmd == "listar":
        _cmd_listar(args)
    elif cmd == "exportar":
        _cmd_exportar(args)
    elif cmd == "resumo":
        _cmd_resumo(args)
    elif cmd == "buscar":
        _cmd_buscar(args)
    else:
        _cmd_buscar(args)


if __name__ == "__main__":
    main()
