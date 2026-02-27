# Leads Scraper Premium 2026

Projeto 100% local para geração de leads com **Google Maps Premium**, enriquecimento de sites e modo procura-serviço.
Interface completa em português brasileiro, com Wizard, Linguagem Natural e Config.

## Requisitos

- Python 3.11+
- Google Chrome/Chromium instalado

## Instalação

```bash
cd leads_scraper
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python -m playwright install chromium --with-deps
```

## Modo Wizard (interativo)

```bash
python main.py
```

## Modo Linguagem Natural

```bash
python main.py --modo natural --texto "buscar 50 clínicas estética brasil vitória es"
python main.py --modo natural --texto "80 advogados portugal lisboa"
python main.py --modo natural --texto "procurar 30 empresas que precisam de site energia solar australia"
python main.py --modo natural --texto "buscar procura-servico 40 clínica estética recife"
```

## Modo Config (config.yaml)

```bash
python main.py --modo config
```

## Debug

```bash
python main.py --headless false --slowmo 250
```

## Saídas

- CSV com colunas exatas:

```
pais,nicho,nome_empresa,cidade,endereco,telefone,email,instagram,site,linkedin,fonte_link,observacoes
```

- JSON com dados brutos completos (campos extras como rating, reviews_count, opening_hours, coordinates, images, etc.)
- SQLite para deduplicação global

## Dicas

- Configure proxies no `.env` para mais estabilidade.
- Use limites menores na primeira execução.
- Alguns sites podem bloquear scraping (best-effort).

## Observações importantes

- O Google Maps e redes sociais podem usar proteção anti-bot.
- O scraper é best-effort e continua mesmo em caso de falhas pontuais.
- Use com responsabilidade e respeite os termos de uso das plataformas.
