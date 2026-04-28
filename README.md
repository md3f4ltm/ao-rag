# sismoGPT

Chat simples para consultar sismos em linguagem natural. Usa LM Studio para interpretar e responder, USGS como fonte de dados, FastAPI no backend e Svelte/Vite no frontend.

## Requisitos

- Docker e Docker Compose
- LM Studio aberto com API em `http://localhost:1234/v1`
- Node.js/npm apenas se quiseres correr o frontend em modo dev fora do Docker

No LM Studio, carrega um modelo de chat/instruct. Modelos de embedding são ignorados no seletor do UI.

## Iniciar com Docker

Na raiz do projeto:

```bash
docker compose up --build
```

O Docker compila o frontend Svelte/Vite, copia o build para o backend e arranca o FastAPI. A aplicação fica toda no mesmo URL:

```text
http://localhost:8000
```

A UI é servida em `/` e a API continua em `/api/...`.

Testar health:

```bash
curl http://localhost:8000/api/health
```

## Iniciar frontend

Este modo é só para desenvolvimento do frontend com hot reload. Para uso normal, `docker compose up --build` já inclui tudo.

Noutro terminal:

```bash
cd frontend
npm install
npm run dev
```

Abre o URL que o Vite mostrar, normalmente:

```text
http://localhost:5173
```

## Base de dados

A base SQLite fica num volume Docker:

```text
ao-rag_earthquake-data
```

Dentro do container:

```text
/data/earthquakes.sqlite3
```

Para apagar containers e a base de dados:

```bash
docker compose down -v
```

## Como funciona

Fluxo normal:

```text
Pergunta -> LLM extrai filtros -> SQLite -> USGS API se faltar dados -> SQLite -> LLM responde
```

Para perguntas como `último sismo em Lisboa`, o backend força uma consulta recente à USGS, grava os eventos na SQLite por `id`, pesquisa a base e só depois pede a resposta final ao LLM.

## Comandos úteis

Parar a aplicação:

```bash
docker compose down
```

Forçar sync recente:

```bash
curl -X POST http://localhost:8000/api/sync
```

Ver modelos disponíveis:

```bash
curl http://localhost:8000/api/models
```
