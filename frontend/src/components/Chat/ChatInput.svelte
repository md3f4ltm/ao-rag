<script>
  import { tick } from 'svelte';
  import { createEventDispatcher } from 'svelte';

  export let loading = false;
  export let value = '';
  
  const dispatch = createEventDispatcher();
  let textarea;

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    
    dispatch('submit', { text: trimmed });
    value = '';
    resizeTextarea();
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  async function resizeTextarea() {
    await tick();
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }
</script>

<div class="input-area">
  <label for="chat-input" class="sr-only">A sua pergunta sobre sismos</label>
  <textarea
    id="chat-input"
    bind:this={textarea}
    bind:value
    on:input={resizeTextarea}
    on:keydown={handleKeydown}
    placeholder="Pergunta sobre sismos"
    rows="1"
    autocomplete="off"
    disabled={loading}
    aria-disabled={loading}
  ></textarea>
  <button 
    on:click={handleSubmit} 
    disabled={loading || !value.trim()}
    aria-label={loading ? "A enviar..." : "Enviar pergunta"}
  >
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      <path d="M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
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
    max-width: 48rem;
    width: 100%;
    margin: 0 auto;
    padding: 1rem 1.5rem calc(1rem + env(safe-area-inset-bottom));
    background: var(--bg);
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
  }

  textarea {
    flex: 1;
    min-height: 54px;
    max-height: 200px;
    padding: 0.8rem 1rem;
    border: 1px solid var(--border);
    border-radius: 0.75rem;
    background: var(--control-bg);
    color: var(--text);
    font-family: inherit;
    font-size: 1rem;
    line-height: 1.5;
    resize: none;
    outline: none;
    overflow-y: auto;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  textarea:focus {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }

  textarea::placeholder {
    color: var(--muted);
  }

  textarea:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button {
    flex-shrink: 0;
    width: 54px;
    height: 54px;
    padding: 0;
    border: 1px solid var(--text);
    border-radius: 0.75rem;
    background: var(--text);
    color: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }

  button:hover:not(:disabled) {
    background: #2563eb;
    border-color: #2563eb;
  }

  button:disabled {
    cursor: not-allowed;
    border-color: var(--border);
    background: var(--hover-bg);
    color: var(--muted);
  }
  
  @media (max-width: 480px) {
    .input-area {
      padding-inline: 1rem;
    }
  }
</style>
