<script>
  import { onDestroy } from 'svelte';

  /** @type {'user' | 'bot'} */
  export let role = 'bot';
  /** @type {string} */
  export let text = '';
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
  $: textParts = linkifyText(text);
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

  function linkifyText(value = '') {
    const pattern = /(https?:\/\/[^\s)]+)/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = pattern.exec(value)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ type: 'text', value: value.slice(lastIndex, match.index) });
      }

      const url = match[0].replace(/[.,;:!?]+$/, '');
      const trailing = match[0].slice(url.length);
      parts.push({ type: 'link', value: url });
      if (trailing) {
        parts.push({ type: 'text', value: trailing });
      }
      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < value.length) {
      parts.push({ type: 'text', value: value.slice(lastIndex) });
    }

    return parts.length ? parts : [{ type: 'text', value }];
  }
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
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9 18h6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              <path d="M10 22h4" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              <path d="M8.6 14.5A6 6 0 1 1 15.4 14.5c-.7.5-1.4 1.4-1.4 2.5h-4c0-1.1-.7-2-1.4-2.5Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
            </svg>
            <span>Thought for {loadingSeconds.toFixed(1)} seconds</span>
          </summary>
          <div class="thinking-lines">
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
                    {#if step.input}
                      <details class="trace-json">
                        <summary>input</summary>
                        <pre>{JSON.stringify(step.input, null, 2)}</pre>
                      </details>
                    {/if}
                    {#if step.output}
                      <details class="trace-json">
                        <summary>output</summary>
                        <pre>{JSON.stringify(step.output, null, 2)}</pre>
                      </details>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <div>A aguardar o primeiro evento do backend.</div>
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
          <div class="trace-list">
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
                {#if step.input}
                  <details class="trace-json">
                    <summary>input</summary>
                    <pre>{JSON.stringify(step.input, null, 2)}</pre>
                  </details>
                {/if}
                {#if step.output}
                  <details class="trace-json">
                    <summary>output</summary>
                    <pre>{JSON.stringify(step.output, null, 2)}</pre>
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

      <div class="message-content">
        {#each textParts as part}
          {#if part.type === 'link'}
            <a href={part.value} target="_blank" rel="noreferrer">{part.value}</a>
          {:else}
            {part.value}
          {/if}
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .message {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 0.5rem;
    color: var(--text);
    line-height: 1.6;
  }

  .message.user {
    justify-content: flex-end;
  }

  .message-body {
    max-width: 100%;
  }

  .message.user .message-body {
    max-width: 65%;
  }

  .message-content {
    white-space: pre-wrap;
    max-width: 100%;
    word-break: break-word;
  }

  .message.assistant .message-content {
    background: transparent;
    border: none;
    border-radius: 0.5rem;
    padding: 0.5rem;
    margin-left: -0.5rem;
    transition: background-color 0.2s ease;
  }

  .message.assistant .message-content:hover {
    background-color: var(--hover-bg);
  }

  .message.user .message-content {
    background-color: var(--user-bg);
    border-radius: 1.25rem;
    padding: 0.8rem 1rem;
    transition: background-color 0.2s ease;
  }

  .message-content a {
    color: #2563eb;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .message-content a:hover {
    color: #1d4ed8;
  }

  .message.user .message-content:hover {
    background-color: var(--user-bg-hover);
  }

  .message.error .message-content {
    background-color: var(--error-bg);
    border: 1px solid var(--error-border);
    color: var(--error-text);
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    margin-top: 0.5rem;
  }

  .trace-info {
    font-size: 0.85rem;
    color: var(--muted);
    margin-bottom: 0.75rem;
  }

  .trace-info summary {
    cursor: pointer;
    user-select: none;
    transition: color 0.2s;
  }
  
  .trace-info summary:hover {
    color: var(--text);
  }

  .trace-info > summary {
    align-items: center;
    background: var(--control-bg);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    display: flex;
    gap: 0.5rem;
    padding: 0.65rem 0.8rem;
    width: min(100%, 360px);
  }

  .loading-trace {
    margin-bottom: 0;
  }

  .thinking-lines {
    background: var(--control-bg);
    border: 1px solid var(--border);
    border-radius: 0.65rem;
    color: var(--text);
    margin-top: 0.5rem;
    padding: 0.8rem 1rem;
  }

  .thinking-lines div + div {
    margin-top: 0.45rem;
  }

  .trace-count {
    background: var(--hover-bg);
    border-radius: 999px;
    color: var(--muted);
    font-size: 0.75rem;
    padding: 0.05rem 0.45rem;
  }

  .trace-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }

  .trace-step {
    background: var(--sidebar-bg);
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    padding: 0.65rem 0.75rem;
  }

  .trace-head {
    align-items: center;
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .trace-kind,
  .trace-status {
    border-radius: 999px;
    font-size: 0.72rem;
    line-height: 1;
    padding: 0.25rem 0.45rem;
  }

  .trace-kind {
    background: var(--hover-bg);
    color: var(--text);
    text-transform: uppercase;
  }

  .trace-kind.tool {
    color: #2563eb;
  }

  .trace-kind.llm {
    color: #059669;
  }

  .trace-kind.system {
    color: var(--muted);
  }

  .trace-name {
    color: var(--text);
    font-weight: 600;
  }

  .trace-status {
    background: var(--control-bg);
    border: 1px solid var(--border);
    color: var(--muted);
    margin-left: auto;
  }

  .trace-status.done,
  .trace-status.success {
    color: #059669;
  }

  .trace-status.error {
    color: var(--error-text);
  }

  .trace-line {
    color: var(--muted);
    font-family: Monaco, Menlo, 'Ubuntu Mono', Consolas, 'Courier New', monospace;
    font-size: 0.78rem;
    margin-top: 0.45rem;
    word-break: break-all;
  }

  .trace-json {
    margin-top: 0.45rem;
  }

  .trace-json summary {
    color: var(--muted);
    font-size: 0.78rem;
  }

  .trace-info pre {
    background: var(--sidebar-bg);
    padding: 0.75rem 1rem;
    border-radius: 8px;
    overflow-x: auto;
    font-family: Monaco, Menlo, 'Ubuntu Mono', Consolas, 'Courier New', monospace;
    font-size: 0.8rem;
    margin-top: 0.5rem;
    color: var(--text);
  }
</style>
