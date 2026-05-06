<script>
  import { createEventDispatcher } from 'svelte';

  export let title = "sismoGPT";
  export let models = [];
  export let selectedModel = '';
  export let darkMode = false;
  export let hidden = false;
  export let showThoughts = true;

  const dispatch = createEventDispatcher();
</script>

<header class:hidden class="header">
  <div class="header-left">
    <button
      class="new-conversation-btn"
      type="button"
      title="Nova conversa"
      aria-label="Nova conversa"
      on:click={() => dispatch('newConversation')}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M12 5v14" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        <path d="M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
      </svg>
    </button>
    <h1 aria-label={title}>{title}</h1>
  </div>
  <div class="header-actions">
    <select
      value={selectedModel}
      aria-label="Selecionar modelo"
      on:change={(event) => dispatch('modelChange', { model: event.currentTarget.value })}
    >
      {#if models.length === 0}
        <option value="">Modelo atual</option>
      {:else}
        {#each models as model}
          <option value={model}>{model}</option>
        {/each}
      {/if}
    </select>

    <button
      class="theme-btn"
      type="button"
      title={darkMode ? 'Modo claro' : 'Modo escuro'}
      aria-label={darkMode ? 'Ativar modo claro' : 'Ativar modo escuro'}
      on:click={() => dispatch('toggleTheme')}
    >
      {#if darkMode}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      {:else}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
        </svg>
      {/if}
    </button>
  </div>
</header>

<style>
  .header {
    background-color: var(--bg);
    padding: 1.25rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 5;
    transition: transform 0.2s ease, opacity 0.2s ease;
  }

  .header.hidden {
    opacity: 0;
    pointer-events: none;
    transform: translateY(-100%);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    min-width: 0;
  }

  h1 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
    color: var(--text);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-width: 0;
  }

  select {
    max-width: min(42vw, 280px);
    height: 32px;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--control-bg);
    color: var(--text);
    font: inherit;
    font-size: 0.9rem;
    padding: 0 0.55rem;
    outline: none;
  }

  .new-conversation-btn,
  .theme-btn {
    width: 32px;
    height: 32px;
    padding: 0;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background-color: var(--control-bg);
    color: var(--muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }

  .new-conversation-btn:hover,
  .theme-btn:hover {
    background-color: var(--hover-bg);
    color: var(--text);
  }

  @media (max-width: 560px) {
    .header {
      align-items: stretch;
      flex-direction: column;
      padding: 1rem;
    }

    .header-actions {
      width: 100%;
    }

    select {
      max-width: none;
      flex: 1;
    }
  }
</style>
