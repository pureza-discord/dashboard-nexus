# Nexus Leads Frontend

SPA React + Vite para o produto Nexus Leads.

## Features

- Landing institucional premium
- Login
- Rotas protegidas em `/app/*`
- Dashboard com filtros avancados
- Analytics com grafico por dia, funil e conversao

## Ambiente

Crie `.env` a partir de `.env.example`:

```bash
VITE_API_BASE_URL=
```

- vazio: usa proxy local do Vite (`/api -> localhost:8000`)
- producao: informe URL do backend (Render/Railway)

## Comandos

```bash
npm install
npm run dev
npm run build
npm run preview
```
