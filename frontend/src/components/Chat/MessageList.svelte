<script>
  import { afterUpdate } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import MessageBubble from './MessageBubble.svelte';

  /** @type {Array<{id?: string, role: 'bot'|'user', text: string, filters?: any, trace?: any[], traceDuration?: number, isLoading?: boolean, isError?: boolean}>} */
  export let messages = [];
  export let loading = false;
  export let showThoughts = true;

  const dispatch = createEventDispatcher();
  let container;
  let lastScrollTop = 0;

  const scrollToBottom = () => {
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  };

  afterUpdate(() => {
    scrollToBottom();
  });

  function handleScroll() {
    if (!container) return;

    const current = container.scrollTop;
    const nearTop = current < 60;

    if (nearTop || current < lastScrollTop - 12) {
      dispatch('headerVisibility', { hidden: false });
    } else if (current > lastScrollTop + 12 && current > 100) {
      dispatch('headerVisibility', { hidden: true });
    }

    lastScrollTop = current;
  }
</script>

<div class="messages-container" bind:this={container} on:scroll={handleScroll} role="log" aria-live="polite">
  <div class="messages-inner">
  {#if messages.length === 0 && !loading}
    <div class="empty-state">
      <p>Pergunta pelos sismos mais recentes, por local, magnitude ou data.</p>
    </div>
  {/if}

  {#each messages as msg}
    <MessageBubble 
      role={msg.role} 
      text={msg.text} 
      currentThought={msg.currentThought}
      filters={msg.filters} 
      trace={msg.trace}
      traceDuration={msg.traceDuration}
      {showThoughts}
      isLoading={msg.isLoading}
      isError={msg.isError}
    />
  {/each}
  </div>
</div>

<style>
  .messages-container {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    background-color: var(--bg);
    scroll-behavior: smooth;
  }

  .messages-inner {
    max-width: 48rem;
    margin: 0 auto;
    padding: 2rem 1.5rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-height: 100%;
  }

  .empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    font-size: 1rem;
    text-align: center;
    padding: 2rem;
  }
</style>
