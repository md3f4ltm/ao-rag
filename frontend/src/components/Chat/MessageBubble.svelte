<script>
  import { onDestroy } from 'svelte';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';

  /** @type {'user' | 'bot'} */
  export let role = 'bot';
  /** @type {string} */
  export let text = '';
  /** @type {string} */
  export let currentThought = '';
  /** @type {Object | null} */
  export let filters = null;
  /** @type {Array<Object> | null} */
  export let trace = null;
  /** @type {number | null} */
  export let traceDuration = null;
  export let showThoughts = true;
  /** @type {boolean} */
  export let isError = false;
  /** @type {boolean} */
  export let isLoading = false;

  let loadingSeconds = 0;
  let intervalId;

  $: messageRoleClass = role === 'user' ? 'user' : 'assistant';
  
  const markedOptions = {
    gfm: true,
    breaks: true,
    mangle: false,
    headerIds: false
  };

  function render(content) {
    if (!content) return '';
    try {
      const rawHtml = marked.parse(content, markedOptions);
      return DOMPurify.sanitize(rawHtml);
    } catch (e) {
      return content;
    }
  }

  $: renderedText = render(text);
  $: renderedThought = render(currentThought);

  $: if (isLoading && !intervalId) {
    const startedAt = Date.now();
    intervalId = setInterval(() => {
      loadingSeconds = Math.max(0.1, (Date.now() - startedAt) / 1000);
    }, 100);
  }
  $: if (!isLoading && intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }

  onDestroy(() => {
    if (intervalId) clearInterval(intervalId);
  });
</script>

<div 
  class="message {messageRoleClass} {isError ? 'error' : ''}"
  role={role === 'bot' ? 'status' : undefined}
>
  {#if isLoading}
    <div class="message-body">
      {#if showThoughts}
        <details class="trace-info loading-trace" open>
          <summary>
            <div class="thinking-spinner"></div>
            <span>Thinking... ({loadingSeconds.toFixed(1)}s)</span>
          </summary>
          <div class="thinking-lines glass">
            {#if currentThought}
              <div class="live-thought">
                {@html renderedThought}
              </div>
            {/if}
            {#if trace && trace.length > 0}
              <div class="trace-list live">
                {#each trace as step}
                  <div class="trace-step">
                    <div class="trace-head">
                      <span class="trace-kind {step.type}">{step.type}</span>
                      <span class="trace-name">{step.name}</span>
                      <span class="trace-status {step.status}">{step.status}</span>
                    </div>
                    {#if step.model}
                      <div class="trace-line">model: {step.model}</div>
                    {/if}
                    {#if step.message}
                      <div class="trace-line">{step.message}</div>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else if !currentThought}
              <div class="waiting-text">A aguardar o primeiro evento do backend...</div>
            {/if}
          </div>
        </details>
      {:else}
        <div class="message-content">A interpretar a pergunta...</div>
      {/if}
    </div>
  {:else}
    <div class="message-body">
      {#if showThoughts && trace && trace.length > 0}
        <details class="trace-info">
          <summary>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9 18h6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              <path d="M10 22h4" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              <path d="M8.6 14.5A6 6 0 1 1 15.4 14.5c-.7.5-1.4 1.4-1.4 2.5h-4c0-1.1-.7-2-1.4-2.5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
            </svg>
            <span>Thought for {traceDuration ?? '...'} seconds</span>
            <span class="trace-count">{trace.length}</span>
          </summary>
          <div class="trace-list glass">
            {#each trace as step}
              <div class="trace-step">
                <div class="trace-head">
                  <span class="trace-kind {step.type}">{step.type}</span>
                  <span class="trace-name">{step.name}</span>
                  <span class="trace-status {step.status}">{step.status}</span>
                </div>
                {#if step.input}
                  <details class="trace-json">
                    <summary>parâmetros</summary>
                    <pre>{JSON.stringify(step.input, null, 2)}</pre>
                  </details>
                {/if}
              </div>
            {/each}
          </div>
        </details>
      {:else if filters && Object.keys(filters).length > 0}
        <details class="trace-info">
          <summary>Filtros aplicados</summary>
          <pre>{JSON.stringify(filters, null, 2)}</pre>
        </details>
      {/if}

      <div class="message-content markdown-body">
        {@html renderedText}
      </div>
    </div>
  {/if}
</div>

<style>
  .message {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 1.5rem;
    color: var(--text);
    line-height: 1.6;
    animation: fadeIn 0.3s ease-out;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .message.user {
    justify-content: flex-end;
  }

  .message-body {
    max-width: 90%;
  }

  .message.user .message-body {
    max-width: 75%;
  }

  .markdown-body {
    font-size: 0.95rem;
    word-break: break-word;
  }

  .message.assistant .markdown-body {
    background: transparent;
    padding: 0.5rem 0;
  }

  .message.user .markdown-body {
    background-color: var(--user-bg);
    border-radius: 1.25rem 1.25rem 0.25rem 1.25rem;
    padding: 0.8rem 1.2rem;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    color: var(--text);
  }

  /* Markdown Elements */
  .markdown-body :global(p) { margin: 1rem 0; }
  .markdown-body :global(p:first-child) { margin-top: 0; }
  .markdown-body :global(p:last-child) { margin-bottom: 0; }

  .markdown-body :global(h1), .markdown-body :global(h2), .markdown-body :global(h3) {
    margin: 1.5rem 0 1rem;
    font-weight: 700;
    color: var(--text);
  }

  .markdown-body :global(h1) { font-size: 1.4rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
  .markdown-body :global(h2) { font-size: 1.2rem; }

  .markdown-body :global(ul), .markdown-body :global(ol) {
    margin: 1rem 0;
    padding-left: 1.5rem;
  }

  .markdown-body :global(li) { margin: 0.4rem 0; }

  .markdown-body :global(table) {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 1.5rem 0;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }

  .markdown-body :global(th) {
    background: var(--sidebar-bg);
    padding: 0.8rem 1rem;
    text-align: left;
    font-weight: 600;
    border-bottom: 2px solid var(--border);
  }

  .markdown-body :global(td) {
    padding: 0.8rem 1rem;
    border-bottom: 1px solid var(--border);
  }

  .markdown-body :global(tr:last-child td) { border-bottom: none; }
  .markdown-body :global(tr:nth-child(even)) { background: var(--hover-bg); }

  .markdown-body :global(code) {
    background: var(--hover-bg);
    padding: 0.2rem 0.4rem;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9em;
  }

  .markdown-body :global(pre) {
    background: #1e293b;
    color: #f1f5f9;
    padding: 1.2rem;
    border-radius: 10px;
    overflow-x: auto;
    margin: 1.5rem 0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }

  .markdown-body :global(pre code) {
    background: transparent;
    padding: 0;
    color: inherit;
  }

  /* Trace & Thinking */
  .trace-info {
    margin-bottom: 1rem;
  }

  .trace-info summary {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.6rem 1rem;
    background: var(--sidebar-bg);
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    cursor: pointer;
    font-size: 0.85rem;
    color: var(--muted);
    width: fit-content;
    transition: all 0.2s;
  }

  .trace-info summary:hover {
    background: var(--hover-bg);
    color: var(--text);
  }

  .glass {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 1rem;
    padding: 1rem;
    margin-top: 0.5rem;
  }

  .thinking-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--muted);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .live-thought {
    font-style: italic;
    color: var(--muted);
    font-size: 0.9rem;
    border-left: 3px solid var(--border);
    padding-left: 1rem;
  }

  .trace-step {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
  }
  .trace-step:last-child { border-bottom: none; }

  .trace-kind {
    font-size: 0.7rem;
    text-transform: uppercase;
    font-weight: 700;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    background: var(--hover-bg);
  }

  .trace-kind.tool { color: #3b82f6; }
  .trace-kind.llm { color: #10b981; }

  .trace-name { font-weight: 600; margin-left: 0.5rem; }
  .trace-status { font-size: 0.75rem; float: right; opacity: 0.7; }

  .error .markdown-body {
    background-color: var(--error-bg);
    border: 1px solid var(--error-border);
    color: var(--error-text);
    padding: 1rem;
    border-radius: 0.75rem;
  }
</style>
