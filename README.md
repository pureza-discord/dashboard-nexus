# Nexus Leads SaaS (AI Market & Sales Intelligence)

Plataforma SaaS multi-tenant para geração de leads, CRM comercial, automação com IA e inteligência de mercado.

## Stack

- Backend: FastAPI + SQLAlchemy
- Banco: PostgreSQL (obrigatório)
- Fila: Redis + Celery worker
- Auth: JWT + bcrypt
- Frontend: React + Vite
- Infra: Docker, Docker Compose, Nginx

## Arquitetura modular

Backend organizado por módulos de produto:

- `auth`
- `users`
- `leads`
- `ai_orchestrator`
- `scraper_service`
- `market_intelligence_service`
- `billing`
- `analytics`

Cada entidade de domínio é isolada por `user_id`:

- `leads`
- `ai_tasks`
- `ai_messages`
- `market_insights`

## Fluxo IA operacional

1. Usuário envia mensagem para `POST /api/ai/chat`
2. `ai_orchestrator` interpreta intenção e extrai parâmetros
3. Backend valida limites de plano (`billing`)
4. Confirmação obrigatória antes de iniciar execução
5. Cria tarefa em `ai_tasks` e dispara Celery (Redis)
6. `scraper_service` ou `market_intelligence_service` executa
7. Progresso e resultado ficam disponíveis em `/api/ai/tasks/{task_id}`
8. Leads são inseridos com `user_id` e deduplicação por fingerprint

## Planos (billing pronto)

- `basic`: 300 leads/mês, sem CSV
- `pro`: 1500 leads/mês, CSV liberado
- `enterprise`: ilimitado, multiusuário preparado

Campos já preparados para Stripe:

- `stripe_customer_id`
- `stripe_subscription_id`

## Pré-requisitos

- Python 3.11+
- Node 20+
- PostgreSQL 15+
- Redis 7+

## Setup local (sem Docker)

```powershell
cd leads_scraper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Configure no `.env`:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`

Backend API:

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload
```

Worker Celery (novo terminal):

```powershell
celery -A server.workers.celery_app.celery_app worker --loglevel=info
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Setup com Docker Compose

```powershell
cd leads_scraper
docker compose up --build
```

Serviços:

- `nginx`: http://localhost
- `api`: interno em `api:8000`
- `worker`: Celery
- `postgres`
- `redis`

Para HTTPS em VPS, use [ssl-example.conf](/c:/Users/filip/Downloads/Scraper/leads_scraper/deploy/nginx/ssl-example.conf) com certificados Let’s Encrypt.

## Endpoints principais

Auth:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

Leads:

- `GET /api/leads`
- `PATCH /api/leads/{lead_id}`
- `POST /api/leads/bulk/status`
- `GET /api/leads/export/csv` (Pro+)

IA:

- `POST /api/ai/chat`
- `GET /api/ai/messages`
- `GET /api/ai/tasks`
- `GET /api/ai/tasks/{task_id}`

Analytics:

- `GET /api/analytics/overview`

Billing:

- `GET /api/billing/usage`
- `GET /api/billing/plans`

Market Intelligence:

- `GET /api/market/reports`

## Scraper mode

Por padrão o sistema usa `SCRAPER_MODE=mock` para ambiente de desenvolvimento.

Para scraping real no backend:

1. Ajuste `SCRAPER_MODE=google_maps`
2. Instale navegador Playwright no ambiente
3. Execute somente no backend/worker (nunca no cliente)

## Segurança aplicada

- JWT validado no backend
- Hash de senha com bcrypt
- Filtragem obrigatória por `user_id`
- Limites de plano validados no backend
- Chaves sensíveis em variáveis de ambiente
- IA/scraper nunca expostos no frontend
