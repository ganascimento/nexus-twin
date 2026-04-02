# Tasks — Feature 01: Project Setup

## Antes de Começar

Leia estes arquivos por completo antes de escrever qualquer código:
- `CLAUDE.md` — estrutura de pastas (§3), stack (§2), dependências (§5), variáveis de ambiente (§6), convenções (§8)
- `.specs/features/01_project_setup/specs.md` — critérios de aceitação

Não leia specs de outras features. Esta feature não tem dependência de nenhuma lógica de negócio.

---

## Plano de Execução

Os Grupos 1–3 podem rodar em paralelo (sem dependências entre si).
O Grupo 4 depende do Grupo 1 estar concluído.
O Grupo 5 é sequencial — roda após todos os outros passarem.

---

### Grupo 1 — Scaffold do Backend (um agente)

**Tarefa:** Criar o projeto Python do backend.

1. Criar `backend/pyproject.toml`:
   - `requires-python = ">=3.11"`
   - Todas as dependências de `CLAUDE.md §5` nas versões mínimas especificadas
   - Build backend: `hatchling`
   - Dev dependencies: `pytest`, `pytest-asyncio`, `httpx` (test client do FastAPI), `langchain` (`FakeListChatModel`)

2. Criar `backend/src/main.py`:
   - Instância do app FastAPI
   - Loguru como logger padrão; interceptar o `logging` da stdlib e rotear pelo Loguru
   - Rota `GET /health` retornando `{"status": "ok"}`
   - Middleware CORS (permitir todas as origens para dev local)

3. Criar `backend/src/database/session.py`:
   - `AsyncSessionLocal` usando driver `asyncpg`
   - `get_db` como async generator dependency
   - Lê `DATABASE_URL` do ambiente — sem valores hardcoded
   - Sem tentativa de conexão no momento do import

4. Criar `backend/alembic.ini` e `backend/src/database/migrations/env.py`:
   - `env.py` lê `DATABASE_URL` do ambiente
   - Suporte a migrations async (`asyncpg`)
   - `target_metadata` deixado como `None` por ora (models chegam na feature 02)

5. Criar todos os arquivos stub (`__init__.py` + `.py` vazios) para cada caminho de `CLAUDE.md §3` dentro de `backend/src/`

6. Criar `backend/.env.example` com todas as variáveis de `CLAUDE.md §6`, valores placeholder e um comentário de uma linha por variável

---

### Grupo 2 — Scaffold do Frontend (um agente)

**Tarefa:** Criar o projeto frontend.

1. Criar `frontend/package.json` com todas as dependências de `CLAUDE.md §5` nas versões especificadas

2. Criar `frontend/tsconfig.json`:
   - Strict mode ativado
   - Path aliases: `@/*` → `src/*`
   - Target: `ES2020`

3. Criar `frontend/vite.config.ts`:
   - Plugin React
   - Proxy `/api` → `http://localhost:8000`

4. Inicializar Tailwind CSS:
   - `frontend/tailwind.config.ts` com content paths cobrindo `src/**/*.{ts,tsx}`
   - `frontend/src/index.css` com as diretivas do Tailwind

5. Criar `frontend/components.json` para o shadcn/ui:
   - Style: `default`
   - Base color: `slate`
   - CSS variables: `true`

6. Criar todos os arquivos stub `.tsx`/`.ts` para cada caminho de `CLAUDE.md §3` dentro de `frontend/src/`:
   - Stubs `.tsx`: `export default function ComponentName() { return null }`
   - Stubs `.ts`: exports vazios `export {}`
   - `frontend/src/App.tsx`: renderiza `<div>Nexus Twin</div>` (suficiente para confirmar que não crasha)

---

### Grupo 3 — Infraestrutura (um agente)

**Tarefa:** Criar o Docker Compose e os arquivos de configuração do projeto.

1. Criar `docker-compose.yml` com os serviços:
   - `postgres`: `postgis/postgis:15-3.4` — porta `5432`, volume `pgdata`, healthcheck `pg_isready`, init script para criar o banco `nexus_twin` e habilitar a extensão PostGIS
   - `redis`: `redis:7-alpine` — porta `6379`, healthcheck `redis-cli ping`
   - `martin`: `ghcr.io/maplibre/martin` — porta `3001`, volume mount para `./geo/data`, depende de `postgres`
   - `valhalla`: `ghcr.io/gis-ops/docker-valhalla/valhalla` — porta `8002`, volume mount para `./geo/data/valhalla_tiles`
   - `backend`: build de `./backend`, porta `8000`, env_file `.env`, depende de `postgres` + `redis`
   - `frontend`: build de `./frontend`, porta `5173`, depende de `backend`

2. Criar `.gitignore` na raiz do projeto:
   - `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`
   - `node_modules/`, `dist/`, `.vite/`
   - `.env` (mas NÃO `.env.example`)
   - Conteúdo de `geo/data/` (adicionar `geo/data/*` e `!geo/data/.gitkeep`)

3. Criar `geo/data/.gitkeep` para que o diretório seja rastreado pelo git

4. Criar `README.md` na raiz — mínimo, apenas o necessário para subir o ambiente local:
   - Pré-requisitos (Docker, Python 3.11+, Node 20+)
   - Setup único de dados geo (download OSM, rodar Planetiler, Valhalla)
   - `docker compose up` para subir todos os serviços
   - Comando `uvicorn` para dev do backend
   - `npm run dev` para dev do frontend

---

### Grupo 4 — Dockerfiles (depende do Grupo 1)

**Tarefa:** Criar os Dockerfiles após a estrutura do backend existir.

1. Criar `backend/Dockerfile`:
   - Base: `python:3.11-slim`
   - Instalar dependências via `pyproject.toml`
   - Entrypoint: `uvicorn src.main:app --host 0.0.0.0 --port 8000`

2. Criar `frontend/Dockerfile`:
   - Multi-stage: build com `node:20-alpine` → serve com `nginx:alpine`
   - Build: `npm ci && npm run build`
   - Serve: copiar `dist/` para o html root do nginx

---

### Grupo 5 — Validação (sequencial, após todos os grupos)

**Tarefa:** Verificar se o scaffold está completo e consistente.

1. Rodar `uvicorn backend/src/main:app --reload` e confirmar que `GET /health` retorna `200`
2. Rodar `npx tsc --noEmit` em `frontend/` e confirmar zero erros
3. Verificar se cada pasta e arquivo listado em `CLAUDE.md §3` existe em `backend/src/` e `frontend/src/`
4. Confirmar que `backend/.env.example` tem todas as variáveis de `CLAUDE.md §6`
5. Rodar `docker compose up postgres redis --wait` e confirmar que ambos os healthchecks passam

Se alguma verificação falhar, corrigir e rodar novamente antes de marcar a feature como concluída.

---

## Condição de Conclusão

Todos os critérios de aceitação em `specs.md` estão satisfeitos e a validação do Grupo 5 passa sem erros.
Atualizar `state.md`: setar o status da feature `01` para `done`.
