# Feature 01 — Project Setup

## Objetivo

Montar a estrutura completa do projeto para que todas as features seguintes tenham uma base funcional e executável. Esta feature entrega zero lógica de negócio — apenas o esqueleto, tooling e conexão da infraestrutura.

---

## Critérios de Aceitação

### Backend

- [ ] `backend/pyproject.toml` existe com todas as dependências de `CLAUDE.md §5` nas versões mínimas especificadas
- [ ] `backend/src/` espelha exatamente a estrutura de pastas de `CLAUDE.md §3` — todos os pacotes têm `__init__.py`, todos os arquivos folha são stubs vazios
- [ ] `uvicorn backend/src/main:app` sobe sem erro e responde `200` em `GET /health`
- [ ] `backend/.env.example` contém todas as variáveis de `CLAUDE.md §6` com valores placeholder e comentários inline
- [ ] `backend/alembic.ini` e `backend/src/database/migrations/env.py` estão configurados para ler `DATABASE_URL` do ambiente
- [ ] `backend/src/database/session.py` exporta `get_db` (dependência async) e `AsyncSessionLocal` — sem conexão real ao banco no momento do import
- [ ] Loguru está configurado como logger padrão em `main.py` — o `logging` da stdlib é interceptado e roteado pelo Loguru

### Frontend

- [ ] `frontend/package.json` tem todas as dependências de `CLAUDE.md §5` nas versões especificadas
- [ ] `frontend/src/` espelha exatamente a estrutura de pastas de `CLAUDE.md §3` — todos os arquivos `.tsx`/`.ts` são stubs vazios que compilam sem erro
- [ ] `npx tsc --noEmit` passa com zero erros
- [ ] Tailwind CSS e shadcn/ui estão inicializados (`tailwind.config.ts`, `components.json`)
- [ ] `frontend/src/App.tsx` renderiza sem crash (shell vazio é suficiente)

### Infraestrutura

- [ ] `docker-compose.yml` define os serviços: `postgres` (imagem PostGIS), `redis`, `valhalla`, `martin`, `backend`, `frontend`
- [ ] `docker compose up postgres redis` sobe ambos os serviços e eles passam nos healthchecks
- [ ] A extensão PostGIS está habilitada no banco `nexus_twin` na primeira inicialização (init script ou healthcheck)
- [ ] Todas as portas dos serviços batem com os valores de `CLAUDE.md §6` (`API_PORT=8000`, `VITE_TILE_SERVER_URL=3001`, `VALHALLA_URL=8002`)
- [ ] `geo/data/` está no `.gitignore` (diretório existe mas conteúdo é excluído)

### Geral

- [ ] `.gitignore` cobre: `__pycache__`, `.venv`, `*.pyc`, `node_modules`, `.env`, `geo/data/`
- [ ] `README.md` na raiz tem o suficiente para um dev novo subir o ambiente local (apenas passos de setup — sem texto introdutório)

---

## Fora do Escopo

- Tabelas e migrations do banco (features 02 e 03)
- Qualquer lógica de negócio, models, repositories ou services
- Download de dados geo ou geração de tiles (preocupação de runtime, não de código)
- Estado ou componentes do frontend além de stubs vazios
- Configuração de CI/CD
