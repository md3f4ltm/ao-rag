<script>
  export let onBack = () => {};

  const runtimePath = [
    {
      label: 'Frontend',
      detail: 'Svelte UI, sessões de chat, streaming SSE e visualização de trace.'
    },
    {
      label: 'FastAPI',
      detail: 'Orquestra pedidos, persiste conversas e executa rotas determinísticas.'
    },
    {
      label: 'Retrieval',
      detail: 'SQLite para eventos sísmicos; Biblioteca Vetorial (ChromaDB) para guias e contexto histórico.'
    },
    {
      label: 'External data',
      detail: 'USGS para eventos; Nominatim apenas quando é preciso resolver um local desconhecido.'
    },
    {
      label: 'LLM local',
      detail: 'LM Studio responde perguntas abertas depois de receber contexto das ferramentas.'
    }
  ];

  const decisionRows = [
    ['Evento factual', '“último sismo no Japão”, “maior sismo em 2024”', 'Parser determinístico + USGS/SQLite'],
    ['Local desconhecido', '“último sismo na Mongólia”', 'Extrair local, geocodificar, consultar bounding box'],
    ['Histórico', '“maior sismo de sempre em Portugal”', 'Resposta histórica conhecida, não USGS recente'],
    ['Segurança civil', '“como me proteger de um sismo”', 'ChromaDB + resposta prática'],
    ['Conhecimento geral', '“o que é uma réplica?”', 'search_library (ChromaDB) e LLM local']
  ];

  const guardrails = [
    'Queries globais nunca recebem latitude 0 / longitude 0 por acidente.',
    'Frases temporais como “últimos 7 dias” não são geocodificadas como locais.',
    '“superior a 5” e variantes são convertidas para magnitude_min.',
    'O limite de apresentação não limita a sincronização USGS antes da ordenação.',
    'Perguntas factuais críticas não dependem da escolha de ferramenta do LLM.'
  ];

  const dataSources = [
    ['USGS FDSN / GeoJSON', 'Eventos modernos, magnitude, tempo, profundidade, coordenadas e URL de evidência.'],
    ['SQLite', 'Cache local pesquisável, histórico sincronizado por janela temporal e filtros espaciais.'],
    ['Nominatim', 'Fallback para transformar locais arbitrários em bounding boxes.'],
    ['ChromaDB', 'Base de dados vetorial com embeddings para pesquisa semântica em manuais e guias.'],
    ['LM Studio', 'Modelo local para formulação final quando a resposta precisa de linguagem natural.']
  ];
</script>

<div class="arch-page">
  <header class="page-header">
    <button class="back-btn" type="button" on:click={onBack}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M19 12H5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        <path d="M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Voltar ao chat
    </button>

    <div class="title-row">
      <div>
        <p class="eyebrow">sismoGPT architecture</p>
        <h1>RAG sísmico com rotas determinísticas</h1>
      </div>
      <span class="status-pill">local-first</span>
    </div>

    <p class="lead">
      O sistema combina retrieval estruturado, documentos de apoio e um LLM local.
      Perguntas factuais seguem código determinístico; o LLM fica para linguagem,
      explicações e síntese com contexto.
    </p>
  </header>

  <main class="content">
    <section class="overview" aria-label="Resumo técnico">
      <div class="metric">
        <span class="metric-label">Primary data</span>
        <strong>USGS</strong>
        <span>eventos sísmicos modernos</span>
      </div>
      <div class="metric">
        <span class="metric-label">Local cache</span>
        <strong>SQLite</strong>
        <span>pesquisa por tempo, magnitude e área</span>
      </div>
      <div class="metric">
        <span class="metric-label">Planner risk</span>
        <strong>bounded</strong>
        <span>rotas críticas não dependem do LLM</span>
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <p class="eyebrow">runtime path</p>
        <h2>Como um pedido é resolvido</h2>
      </div>

      <div class="system-map">
        {#each runtimePath as step, index}
          <article class="system-node">
            <span class="node-index">{index + 1}</span>
            <h3>{step.label}</h3>
            <p>{step.detail}</p>
          </article>
        {/each}
      </div>
    </section>

    <section class="section split">
      <div class="section-heading">
        <p class="eyebrow">routing</p>
        <h2>Decisão antes do LLM</h2>
        <p>
          O backend tenta primeiro reconhecer perguntas sísmicas estruturadas.
          Isto evita loops de ferramentas e respostas erradas quando o modelo local
          escolhe a fonte errada.
        </p>
      </div>

      <div class="decision-table" role="table" aria-label="Tabela de rotas">
        <div class="table-row table-head" role="row">
          <span>Tipo</span>
          <span>Exemplo</span>
          <span>Rota</span>
        </div>
        {#each decisionRows as row}
          <div class="table-row" role="row">
            <span>{row[0]}</span>
            <span>{row[1]}</span>
            <span>{row[2]}</span>
          </div>
        {/each}
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <p class="eyebrow">data layer</p>
        <h2>Fontes e responsabilidades</h2>
      </div>

      <div class="source-list">
        {#each dataSources as source}
          <article>
            <h3>{source[0]}</h3>
            <p>{source[1]}</p>
          </article>
        {/each}
      </div>
    </section>

    <section class="section split">
      <div class="section-heading">
        <p class="eyebrow">failure modes</p>
        <h2>Guardrails implementados</h2>
        <p>
          Estes controlos existem porque os erros observados em produção eram
          quase sempre de parsing: local confundido com tempo, limites aplicados
          cedo demais, ou ferramenta errada.
        </p>
      </div>

      <ul class="guardrail-list">
        {#each guardrails as item}
          <li>{item}</li>
        {/each}
      </ul>
    </section>

    <section class="section notes">
      <div>
        <p class="eyebrow">known limits</p>
        <h2>O que ainda não é catálogo histórico completo</h2>
      </div>
      <p>
        A USGS cobre bem eventos modernos, mas não substitui um catálogo histórico
        nacional. Casos como Lisboa 1755 precisam de tratamento histórico explícito
        ou de uma fonte histórica curada. O sistema já evita responder “últimos
        365 dias” para perguntas “de sempre”, mas a cobertura histórica completa
        deve ser uma camada própria.
      </p>
    </section>
  </main>
</div>

<style>
  .arch-page {
    height: 100%;
    overflow-y: auto;
    background: var(--bg);
    color: var(--text);
    padding: 2rem;
  }

  .page-header,
  .content {
    max-width: 1080px;
    margin: 0 auto;
  }

  .page-header {
    padding-bottom: 1.75rem;
    border-bottom: 1px solid var(--border);
  }

  .back-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    min-height: 2.25rem;
    margin-bottom: 1.5rem;
    padding: 0 0.75rem;
    border: 1px solid var(--border);
    border-radius: 0.45rem;
    background: var(--control-bg);
    color: var(--muted);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .back-btn:hover {
    background: var(--hover-bg);
    color: var(--text);
  }

  .title-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .eyebrow {
    margin: 0 0 0.45rem;
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  h1,
  h2,
  h3,
  p {
    letter-spacing: 0;
  }

  h1 {
    margin: 0;
    font-size: 2rem;
    line-height: 1.15;
    font-weight: 750;
  }

  h2 {
    margin: 0;
    font-size: 1.25rem;
    line-height: 1.25;
  }

  h3 {
    margin: 0;
    font-size: 0.95rem;
  }

  .lead {
    max-width: 760px;
    margin: 1rem 0 0;
    color: var(--muted);
    font-size: 1rem;
    line-height: 1.6;
  }

  .status-pill {
    flex-shrink: 0;
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    background: var(--control-bg);
    font-size: 0.75rem;
    font-weight: 700;
  }

  .content {
    padding: 1.75rem 0 3rem;
  }

  .overview {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    margin-bottom: 2.5rem;
  }

  .metric,
  .system-node,
  .source-list article,
  .notes {
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--sidebar-bg);
  }

  .metric {
    padding: 1rem;
  }

  .metric-label {
    display: block;
    color: var(--muted);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
  }

  .metric strong {
    display: block;
    margin-top: 0.4rem;
    font-size: 1.25rem;
  }

  .metric span:last-child {
    display: block;
    margin-top: 0.3rem;
    color: var(--muted);
    font-size: 0.85rem;
    line-height: 1.35;
  }

  .section {
    margin-top: 2.5rem;
  }

  .section-heading {
    max-width: 760px;
    margin-bottom: 1rem;
  }

  .section-heading p:not(.eyebrow) {
    margin: 0.7rem 0 0;
    color: var(--muted);
    line-height: 1.6;
  }

  .system-map {
    display: grid;
    grid-template-columns: repeat(5, minmax(150px, 1fr));
    gap: 0.75rem;
  }

  .system-node {
    position: relative;
    min-height: 10rem;
    padding: 1rem;
  }

  .system-node::after {
    content: '';
    position: absolute;
    top: 1.55rem;
    right: -0.75rem;
    width: 0.75rem;
    border-top: 1px solid var(--border);
  }

  .system-node:last-child::after {
    display: none;
  }

  .node-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.7rem;
    height: 1.7rem;
    margin-bottom: 0.9rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--muted);
    font-size: 0.8rem;
    font-weight: 700;
  }

  .system-node p,
  .source-list p,
  .notes p,
  .guardrail-list li {
    color: var(--muted);
    font-size: 0.88rem;
    line-height: 1.55;
  }

  .system-node p,
  .source-list p {
    margin: 0.55rem 0 0;
  }

  .split {
    display: grid;
    grid-template-columns: minmax(240px, 0.75fr) minmax(0, 1.25fr);
    gap: 1.5rem;
    align-items: start;
  }

  .decision-table {
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    overflow: hidden;
  }

  .table-row {
    display: grid;
    grid-template-columns: 0.8fr 1.2fr 1fr;
    gap: 1rem;
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.86rem;
  }

  .table-row:last-child {
    border-bottom: 0;
  }

  .table-row span:first-child,
  .table-head {
    color: var(--text);
    font-weight: 700;
  }

  .table-head {
    background: var(--sidebar-bg);
    font-size: 0.76rem;
    text-transform: uppercase;
  }

  .source-list {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.75rem;
  }

  .source-list article {
    padding: 1rem;
  }

  .guardrail-list {
    display: grid;
    gap: 0.6rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .guardrail-list li {
    padding: 0.8rem 0.9rem;
    border-left: 3px solid var(--border);
    background: var(--sidebar-bg);
    border-radius: 0.35rem;
  }

  .notes {
    display: grid;
    grid-template-columns: minmax(220px, 0.7fr) minmax(0, 1.3fr);
    gap: 1.25rem;
    padding: 1.25rem;
  }

  .notes p {
    margin: 0;
  }

  @media (max-width: 980px) {
    .overview,
    .system-map,
    .source-list {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .system-node::after {
      display: none;
    }

    .split,
    .notes {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .arch-page {
      padding: 1rem;
    }

    .title-row {
      flex-direction: column;
    }

    h1 {
      font-size: 1.55rem;
    }

    .overview,
    .system-map,
    .source-list {
      grid-template-columns: 1fr;
    }

    .table-row {
      grid-template-columns: 1fr;
      gap: 0.35rem;
    }
  }
</style>
