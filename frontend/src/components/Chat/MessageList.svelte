<script>
  import { afterUpdate } from 'svelte';
  import MessageBubble from './MessageBubble.svelte';

  /** @type {Array<{role: 'bot'|'user', text: string, filters?: any, isError?: boolean}>} */
  export let messages = [];
  export let loading = false;

  let container;

  const scrollToBottom = () => {
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  };

  afterUpdate(() => {
    scrollToBottom();
  });
</script>

<div class="messages-container" bind:this={container} role="log" aria-live="polite">
  {#if messages.length === 0 && !loading}
    <div class="empty-state">
      <p>Inicie a conversa fazendo uma pergunta.</p>
    </div>
  {/if}

  {#each messages as msg}
    <MessageBubble 
      role={msg.role} 
      text={msg.text} 
      filters={msg.filters} 
      isError={msg.isError}
    />
  {/each}

  {#if loading}
    <MessageBubble role="bot" isLoading={true} />
  {/if}
</div>

<style>
  .messages-container {
    flex: 1;
    padding: clamp(1.5rem, 4vw, 2rem);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    /* Smooth scroll behavior */
    scroll-behavior: smooth;
  }

  .empty-state {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    font-size: 1.1rem;
    text-align: center;
    padding: 2rem;
  }
</style>
