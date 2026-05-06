<script>
  import { tick } from 'svelte';
  import { createEventDispatcher } from 'svelte';

  export let loading = false;
  export let value = '';
  export let allowedTools = [
    'sync_recent_earthquakes',
    'sync_earthquake_history',
    'search_earthquakes',
    'search_library'
  ];
  
  const dispatch = createEventDispatcher();
  let textarea;
  let showToolsMenu = false;

  const tools = [
    { 
      id: 'sync_recent_earthquakes', 
      label: 'Dados em Tempo Real', 
      tag: 'EXTERNAL API (USGS)',
      icon: '🌍',
      description: 'Acede aos sismos mais recentes no mundo.' 
    },
    { 
      id: 'sync_earthquake_history', 
      label: 'Arquivo Histórico', 
      tag: 'EXTERNAL API (USGS)',
      icon: '📚',
      description: 'Procura sismos antigos e estatísticas por data.' 
    },
    { 
      id: 'search_earthquakes', 
      label: 'Base de Dados Local', 
      tag: 'SQL DB (SQLite)',
      icon: '🔎',
      description: 'Pesquisa rápida nos sismos já guardados localmente.' 
    },
    { 
      id: 'search_library', 
      label: 'Guias de Segurança', 
      tag: 'RAG / VECTOR DB (ChromaDB)',
      icon: '📖',
      description: 'Consulta manuais de proteção civil e guias técnicos.' 
    }
  ];

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    
    dispatch('submit', { text: trimmed });
    value = '';
    resizeTextarea();
    showToolsMenu = false;
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

  function toggleTool(id) {
    if (allowedTools.includes(id)) {
      allowedTools = allowedTools.filter(t => t !== id);
    } else {
      allowedTools = [...allowedTools, id];
    }
    dispatch('toolsChange', { tools: allowedTools });
  }

  function toggleToolsMenu() {
    showToolsMenu = !showToolsMenu;
  }
</script>

<div class="chat-input-container">
  {#if showToolsMenu}
    <div class="tools-menu">
      <div class="menu-header">
        <span>Fontes de Dados e Ferramentas</span>
        <button class="close-menu" on:click={() => showToolsMenu = false}>×</button>
      </div>
      <div class="tools-list">
        {#each tools as tool}
          <button
            type="button"
            class="tool-item"
            class:active={allowedTools.includes(tool.id)}
            on:click={() => toggleTool(tool.id)}
            disabled={loading}
          >
            <span class="tool-icon">{tool.icon}</span>
            <div class="tool-info">
              <span class="tool-label">{tool.label}</span>
              <span class="tool-tag">{tool.tag}</span>
              <span class="tool-desc">{tool.description}</span>
            </div>
            <div class="tool-checkbox">
              <div class="check-inner"></div>
            </div>
          </button>
        {/each}
      </div>
    </div>
  {/if}

  <div class="input-area">
    <button 
      class="tools-toggle-btn" 
      class:active={showToolsMenu}
      on:click={toggleToolsMenu}
      title="Configurar ferramentas"
      aria-label="Abrir menu de ferramentas"
      disabled={loading}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 5V19M5 12H19" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>

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
      class="send-btn"
      on:click={handleSubmit} 
      disabled={loading || !value.trim()}
      aria-label={loading ? "A enviar..." : "Enviar pergunta"}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        <path d="M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
  </div>
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

  .chat-input-container {
    max-width: 48rem;
    width: 100%;
    margin: 0 auto;
    padding: 0.5rem 1.5rem calc(1rem + env(safe-area-inset-bottom));
    background: var(--bg);
    display: flex;
    flex-direction: column;
    position: relative;
  }

  .tools-menu {
    position: absolute;
    bottom: 100%;
    left: 1.5rem;
    right: 1.5rem;
    background: var(--control-bg);
    border: 1px solid var(--border);
    border-radius: 1rem;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
    margin-bottom: 0.75rem;
    z-index: 100;
    overflow: hidden;
    animation: slideUp 0.2s ease-out;
  }

  @keyframes slideUp {
    from { transform: translateY(10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .menu-header {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--muted);
  }

  .close-menu {
    background: transparent;
    border: none;
    color: var(--muted);
    font-size: 1.5rem;
    line-height: 1;
    cursor: pointer;
    padding: 0;
  }

  .tools-list {
    padding: 0.5rem;
    display: grid;
    gap: 0.25rem;
  }

  .tool-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    border: none;
    border-radius: 0.75rem;
    background: transparent;
    color: var(--text);
    text-align: left;
    cursor: pointer;
    transition: background 0.2s;
  }

  .tool-item:hover {
    background: var(--hover-bg);
  }

  .tool-icon {
    font-size: 1.5rem;
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg);
    border-radius: 0.5rem;
  }

  .tool-info {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .tool-label {
    font-weight: 600;
    font-size: 0.9rem;
  }

  .tool-tag {
    font-size: 0.65rem;
    font-weight: 700;
    color: #2563eb;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    margin-top: 0.1rem;
  }

  .tool-desc {
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 0.2rem;
  }

  .tool-checkbox {
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid var(--border);
    border-radius: 0.35rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .tool-item.active .tool-checkbox {
    background: #2563eb;
    border-color: #2563eb;
  }

  .check-inner {
    width: 0.5rem;
    height: 0.25rem;
    border-left: 2px solid white;
    border-bottom: 2px solid white;
    transform: rotate(-45deg) translateY(-1px);
    opacity: 0;
  }

  .tool-item.active .check-inner {
    opacity: 1;
  }

  .input-area {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
  }

  .tools-toggle-btn {
    width: 42px;
    height: 42px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--control-bg);
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 6px;
  }

  .tools-toggle-btn:hover {
    border-color: var(--muted);
    color: var(--text);
  }

  .tools-toggle-btn.active {
    background: #2563eb;
    border-color: #2563eb;
    color: white;
    transform: rotate(45deg);
  }

  textarea {
    flex: 1;
    min-height: 54px;
    max-height: 200px;
    padding: 0.8rem 1rem;
    border: 1px solid var(--border);
    border-radius: 1.5rem;
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
    border-color: var(--muted);
  }

  .send-btn {
    flex-shrink: 0;
    width: 42px;
    height: 42px;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: var(--text);
    color: var(--bg);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 6px;
  }

  .send-btn:hover:not(:disabled) {
    opacity: 0.8;
  }

  .send-btn:disabled {
    cursor: not-allowed;
    background: var(--border);
    color: var(--muted);
  }
  
  @media (max-width: 480px) {
    .chat-input-container {
      padding-inline: 1rem;
    }
    .tools-menu {
      left: 1rem;
      right: 1rem;
    }
  }
</style>
