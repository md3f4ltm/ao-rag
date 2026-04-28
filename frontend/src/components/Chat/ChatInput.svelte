<script>
  import { createEventDispatcher } from 'svelte';

  export let loading = false;
  export let value = '';
  
  const dispatch = createEventDispatcher();

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    
    dispatch('submit', { text: trimmed });
    value = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>

<div class="input-area">
  <label for="chat-input" class="sr-only">A sua pergunta sobre sismos</label>
  <input 
    id="chat-input"
    type="text" 
    bind:value
    on:keydown={handleKeydown}
    placeholder="Escreva a sua pergunta aqui... (ex: sismos nos Açores)" 
    autocomplete="off"
    disabled={loading}
    aria-disabled={loading}
  />
  <button 
    on:click={handleSubmit} 
    disabled={loading || !value.trim()}
    aria-label={loading ? "A enviar..." : "Enviar pergunta"}
  >
    {#if loading}
      A enviar...
    {:else}
      Enviar
    {/if}
  </button>
</div>

<style>
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
  }

  .input-area {
    padding: clamp(1rem, 3vw, 1.5rem);
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-top: 1px solid var(--card-border);
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  input[type="text"] {
    flex: 1;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: clamp(0.75rem, 2vw, 1rem) clamp(1rem, 2vw, 1.5rem);
    color: white;
    font-family: inherit;
    font-size: 1rem;
    outline: none;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }

  input[type="text"]:focus {
    border-color: var(--primary);
    background: rgba(255, 255, 255, 0.08);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
  }

  input[type="text"]::placeholder {
    color: #64748b;
  }

  input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button {
    background: linear-gradient(135deg, var(--primary), var(--primary-hover));
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0 clamp(1.2rem, 3vw, 2rem);
    height: 100%;
    min-height: 48px;
    font-family: inherit;
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
    white-space: nowrap;
  }

  button:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 12px -3px rgba(59, 130, 246, 0.4);
  }

  button:active:not(:disabled) {
    transform: translateY(0);
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background: #475569;
    box-shadow: none;
  }
  
  @media (max-width: 480px) {
    .input-area {
      flex-direction: column;
    }
    button {
      width: 100%;
    }
  }
</style>
