<script>
  import LoadingDots from './LoadingDots.svelte';

  /** @type {'user' | 'bot'} */
  export let role = 'bot';
  /** @type {string} */
  export let text = '';
  /** @type {Object | null} */
  export let filters = null;
  /** @type {boolean} */
  export let isError = false;
  /** @type {boolean} */
  export let isLoading = false;

  // Render text with line breaks
  $: formattedText = text ? text.replace(/\n/g, '<br/>') : '';
</script>

<div 
  class="message {role === 'user' ? 'user-message' : 'bot-message'} {isError ? 'error-message' : ''}"
  role={role === 'bot' ? 'status' : undefined}
>
  {#if isLoading}
    <LoadingDots label="A interpretar a pergunta" />
  {:else}
    <!-- eslint-disable-next-line svelte/no-at-html-tags -->
    <div class="content">{@html formattedText}</div>
    
    {#if filters && Object.keys(filters).length > 0}
      <details class="filters-info">
        <summary>Filtros aplicados</summary>
        <pre>{JSON.stringify(filters, null, 2)}</pre>
      </details>
    {/if}
  {/if}
</div>

<style>
  .message {
    max-width: 85%;
    padding: 1rem 1.5rem;
    border-radius: 18px;
    line-height: 1.6;
    animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    word-break: break-word;
  }

  @keyframes slideIn {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .user-message {
    align-self: flex-end;
    background: var(--user-msg);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-bottom-right-radius: 4px;
    color: #eff6ff;
  }

  .bot-message {
    align-self: flex-start;
    background: var(--bot-msg);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-bottom-left-radius: 4px;
    color: #f8fafc;
  }

  .error-message {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }

  .content :global(strong) {
    color: inherit;
    font-weight: 600;
  }

  .filters-info {
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 1rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .filters-info summary {
    cursor: pointer;
    user-select: none;
    transition: color 0.2s;
  }
  
  .filters-info summary:hover {
    color: #cbd5e1;
  }

  .filters-info pre {
    background: rgba(0,0,0,0.2);
    padding: 0.5rem;
    border-radius: 8px;
    overflow-x: auto;
    font-family: 'Fira Code', monospace;
    font-size: 0.8rem;
    margin-top: 0.5rem;
  }
</style>
