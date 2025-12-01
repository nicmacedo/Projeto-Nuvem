
# Chat em Nuvem (Render) - Enhanced

Projeto pronto para deploy no Render com:
- FastAPI backend
- WebSocket em tempo real
- Suporte opcional a Redis Pub/Sub (configure REDIS_URL)
- Endpoints REST para histórico (/api/messages)
- Dashboard simples para demonstrar instância/processo e conexões
- Frontend estilizado em `app/static/index.html`
- Script de stress WebSocket (scripts/stress-ws.js)

## Deploy no Render
1. Crie repositório no GitHub com este conteúdo.
2. No Render, crie um Web Service apontando para o repo.
3. Set env vars se usar Redis:
   - REDIS_URL (ex: redis://:password@host:6379/0)
4. Start Command (Render) - já no Procfile:
   - `gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT`
5. Acesse `/` para frontend, `/dashboard` para dashboard.

## Testes
- WebSocket endpoint: `wss://<seu-app>.onrender.com/ws`
- REST history: `GET /api/messages`
- REST post: `POST /api/messages` body `{"author":"Nome","text":"Olá"}`

Se quiser que eu conecte o banco Postgres também e adicione persistência, eu integro.
