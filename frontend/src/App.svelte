<script>
  import { onMount } from 'svelte';
  import Header from './components/Layout/Header.svelte';
  import MessageList from './components/Chat/MessageList.svelte';
  import ChatInput from './components/Chat/ChatInput.svelte';
  import ArchitecturePage from './components/Architecture/ArchitecturePage.svelte';

  const initialMessage = {
    role: 'bot',
    text: `Olá! Sou o sismoGPT. Podes perguntar-me sobre sismos, por exemplo:\n\n• "Qual foi o último sismo em Portugal?"\n• "Sismos com magnitude superior a 5 nos últimos 7 dias"\n• "Houve sismos perto dos Açores?"`,
    filters: null,
    isError: false
  };

  const createConversation = () => ({
    id: crypto.randomUUID(),
    title: 'Novo chat',
    messages: [initialMessage]
  });

  let conversations = [];
  let activeConversationId = null;
  let models = [];
  let selectedModel = '';
  let darkMode = false;
  let loading = false;
  let inputValue = '';
  let sidebarCollapsed = false;
  let topBarHidden = false;
  let showThoughts = true;
  let currentView = 'chat'; // 'chat' | 'architecture'

  $: activeConversation = conversations.find((chat) => chat.id === activeConversationId);
  $: messages = activeConversation?.messages || [];

  onMount(async () => {
    document.body.dataset.theme = darkMode ? 'dark' : 'light';

    // Load sessions
    try {
      const res = await fetch('/api/sessions');
      const data = await res.json();
      if (data.sessions && data.sessions.length > 0) {
        conversations = data.sessions.map(s => ({
          id: s.id,
          title: s.title,
          messages: [] // Will load on demand
        }));
        activeConversationId = conversations[0].id;
        loadSessionMessages(activeConversationId);
      } else {
        newConversation();
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
      newConversation();
    }

    try {
      const res = await fetch('/api/models');
      const data = await res.json();
      models = (data.models || []).filter((model) => !model.toLowerCase().includes('embedding'));
      if (models.length === 0 && data.default_model && !data.default_model.toLowerCase().includes('embedding')) {
        models = [data.default_model];
      }
      selectedModel = models.includes(data.default_model) ? data.default_model : models[0] || '';
    } catch (error) {
      models = [];
    }
  });

  async function loadSessionMessages(sessionId) {
    const conv = conversations.find(c => c.id === sessionId);
    if (conv && conv.messages.length > 0) return;

    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
      const data = await res.json();
      updateConversation(sessionId, (chat) => ({
        ...chat,
        messages: data.messages.length > 0 ? data.messages.map(m => ({
          role: m.role === 'bot' ? 'bot' : 'user',
          text: m.content,
          trace: m.trace,
          traceDuration: m.trace_duration,
          filters: m.filters,
          isError: m.is_error
        })) : [initialMessage]
      }));
    } catch (error) {
      console.error('Failed to load messages:', error);
    }
  }

  function updateConversation(id, updater) {
    conversations = conversations.map((chat) => (
      chat.id === id ? updater(chat) : chat
    ));
  }

  function updateActiveConversation(updater) {
    if (activeConversationId) {
      updateConversation(activeConversationId, updater);
    }
  }

  function newConversation() {
    const chat = createConversation();
    conversations = [chat, ...conversations];
    activeConversationId = chat.id;
    inputValue = '';
  }

  async function deleteConversation(id, event) {
    event.stopPropagation();
    try {
      await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
      conversations = conversations.filter(c => c.id !== id);
      if (activeConversationId === id) {
        if (conversations.length > 0) {
          activeConversationId = conversations[0].id;
          loadSessionMessages(activeConversationId);
        } else {
          newConversation();
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  }

  function selectConversation(id) {
    if (loading) return;
    activeConversationId = id;
    inputValue = '';
    loadSessionMessages(id);
  }

  function toggleTheme() {
    darkMode = !darkMode;
    document.body.dataset.theme = darkMode ? 'dark' : 'light';
  }

  function toggleSidebar() {
    sidebarCollapsed = !sidebarCollapsed;
  }

  function toggleThoughts() {
    showThoughts = !showThoughts;
  }

  function handleHeaderVisibility(event) {
    topBarHidden = event.detail.hidden;
  }

  function handleModelChange(event) {
    selectedModel = event.detail.model;
  }

  function buildHistory(chat) {
    return (chat?.messages || [])
      .filter((msg) => msg !== initialMessage && !msg.isLoading && msg.text)
      .slice(-12)
      .map((msg) => ({
        role: msg.role === 'bot' ? 'assistant' : 'user',
        content: msg.text
      }));
  }

  async function handleSendMessage(event) {
    const userMsg = event.detail.text;
    if (!userMsg) return;

    const targetConversationId = activeConversationId;
    const targetConversation = conversations.find((chat) => chat.id === targetConversationId);
    const history = buildHistory(targetConversation);
    const botMessageId = crypto.randomUUID();

    const newTitle = targetConversation?.title === 'Novo chat' ? userMsg.slice(0, 42) : targetConversation?.title;
    updateConversation(targetConversationId, (chat) => ({
      ...chat,
      title: newTitle || chat.title,
      messages: [
        ...chat.messages,
        { role: 'user', text: userMsg },
        { id: botMessageId, role: 'bot', text: '', trace: [], traceDuration: 0, isLoading: true, currentThought: '' }
      ]
    }));
    loading = true;

    const updateBotMessage = (patch) => {
      updateConversation(targetConversationId, (chat) => ({
        ...chat,
        messages: chat.messages.map((msg) => (
          msg.id === botMessageId ? { ...msg, ...patch } : msg
        ))
      }));
    };

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userMsg,
          session_id: targetConversationId,
          model: selectedModel || undefined,
          client_time: new Date().toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          history
        })
      });

      if (!res.ok || !res.body) {
        throw new Error('Erro ao comunicar com a API do servidor.');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() || '';

        for (const chunk of chunks) {
          const line = chunk.split('\n').find((entry) => entry.startsWith('data: '));
          if (!line) continue;

          let data;
          try {
            data = JSON.parse(line.slice(6));
          } catch (e) {
            continue;
          }

          if (data.event === 'thought') {
            const currentMsg = conversations.find(c => c.id === targetConversationId)?.messages.find(m => m.id === botMessageId);
            const updatedThought = (currentMsg?.currentThought || '') + data.thought;
            updateBotMessage({
              currentThought: updatedThought,
              isLoading: true
            });
          }

          if (data.event === 'trace') {
            updateBotMessage({
              trace: data.trace,
              traceDuration: data.trace_duration_seconds,
              isLoading: true
            });
          }

          if (data.event === 'done') {
            const isErrorResponse = data.response.includes('⚠️ **Erro**:') || data.response.includes('**Erro**:');
            updateBotMessage({
              text: data.response,
              filters: data.filters_extracted,
              trace: data.trace,
              traceDuration: data.trace_duration_seconds,
              isLoading: false,
              isError: isErrorResponse,
              currentThought: ''
            });
          }

          if (data.event === 'error') {
            updateBotMessage({
              text: data.message || 'Ocorreu um erro ao processar a resposta.',
              isLoading: false,
              isError: true
            });
          }
        }
      }
    } catch (error) {
      updateBotMessage({
        text: error.message || 'Não foi possível ligar ao servidor. Verifique a ligação.',
        isLoading: false,
        isError: true
      });
    } finally {
      loading = false;
    }
  }
</script>

<main class="container">
  <aside class:collapsed={sidebarCollapsed} class="sidebar" aria-label="Conversas">
    <div class="sidebar-actions">
      <button
        class="collapse-chat"
        type="button"
        title={sidebarCollapsed ? 'Mostrar chats' : 'Esconder chats'}
        aria-label={sidebarCollapsed ? 'Mostrar chats' : 'Esconder chats'}
        on:click={toggleSidebar}
      >
        {sidebarCollapsed ? '›' : '‹'}
      </button>
      {#if !sidebarCollapsed}
        <button class="new-chat" type="button" on:click={newConversation}>Novo chat</button>
      {/if}
    </div>
    {#if !sidebarCollapsed}
      <div class="chat-tabs">
        {#each conversations as chat (chat.id)}
          <div class="chat-tab-wrapper">
            <button
              class="chat-tab"
              class:active={chat.id === activeConversationId && currentView === 'chat'}
              type="button"
              on:click={() => { currentView = 'chat'; selectConversation(chat.id); }}
            >
              {chat.title}
            </button>
            <button
              class="delete-chat"
              type="button"
              title="Eliminar"
              aria-label={`Eliminar conversa ${chat.title}`}
              on:click|stopPropagation={(e) => deleteConversation(chat.id, e)}
            >
              ×
            </button>
          </div>
        {/each}
      </div>
      <button
        class="arch-tab"
        class:active={currentView === 'architecture'}
        type="button"
        on:click={() => currentView = 'architecture'}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2"/>
          <rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2"/>
          <rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2"/>
          <rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="2"/>
        </svg>
        Arquitetura
      </button>
    {/if}
  </aside>

  <section class="chat-shell" aria-label="Interface de conversação">
    {#if currentView === 'architecture'}
      <ArchitecturePage onBack={() => currentView = 'chat'} />
    {:else}
      <Header
        title="sismoGPT"
        {models}
        {selectedModel}
        {darkMode}
        hidden={topBarHidden}
        {showThoughts}
        on:newConversation={newConversation}
        on:modelChange={handleModelChange}
        on:toggleTheme={toggleTheme}
        on:toggleThoughts={toggleThoughts}
      />
      <div class="chat-wrapper">
        <MessageList {messages} {loading} {showThoughts} on:headerVisibility={handleHeaderVisibility} />
        <ChatInput
          bind:value={inputValue}
          {loading}
          on:submit={handleSendMessage}
        />
      </div>
    {/if}
  </section>
</main>

<style>
  .container {
    width: 100%;
    min-height: 100dvh;
    height: 100dvh;
    display: flex;
    background: var(--bg);
    color: var(--text);
    overflow: hidden;
  }

  .sidebar {
    height: 100dvh;
    width: 240px;
    flex-shrink: 0;
    border-right: 1px solid var(--border);
    background: var(--sidebar-bg);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    overflow: hidden;
    transition: width 0.2s ease, padding 0.2s ease;
  }

  .sidebar.collapsed {
    align-items: center;
    padding: 1rem 0.5rem;
    width: 52px;
  }

  .sidebar-actions {
    display: flex;
    gap: 0.5rem;
  }

  .sidebar.collapsed .sidebar-actions {
    justify-content: center;
  }

  .new-chat,
  .collapse-chat {
    height: 38px;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--control-bg);
    color: var(--text);
    font: inherit;
    cursor: pointer;
  }

  .collapse-chat {
    width: 38px;
    flex-shrink: 0;
    font-size: 1.25rem;
    line-height: 1;
  }

  .new-chat {
    flex: 1;
  }

  .new-chat:hover,
  .collapse-chat:hover {
    background: var(--hover-bg);
  }

  .chat-tabs {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-height: 0;
    overflow-y: auto;
  }

  .chat-tab-wrapper {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 2rem;
    align-items: center;
    gap: 0.2rem;
  }

  .delete-chat {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    min-width: 2rem;
    opacity: 0.65;
    background: transparent;
    border: none;
    border-radius: 0.4rem;
    color: var(--muted);
    font-size: 1.2rem;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    overflow: visible;
    text-align: center;
    white-space: nowrap;
    transition: opacity 0.2s, color 0.2s, background 0.2s;
  }

  .delete-chat:hover {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error-text);
  }

  .chat-tab {
    min-width: 0;
  }

  .chat-tabs .chat-tab {
    width: 100%;
    border: 0;
    border-radius: 0.5rem;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font: inherit;
    padding: 0.7rem 0.75rem;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chat-tabs .chat-tab:hover,
  .chat-tabs .chat-tab.active {
    background: var(--hover-bg);
    color: var(--text);
  }

  .arch-tab {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    margin-top: auto;
    padding: 0.75rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--control-bg);
    color: var(--muted);
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  .arch-tab:hover {
    background: var(--hover-bg);
    color: var(--text);
  }

  .arch-tab.active {
    background: var(--hover-bg);
    color: var(--text);
    border-color: var(--muted);
  }

  .chat-shell {
    min-width: 0;
    min-height: 0;
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100dvh;
    overflow: hidden;
  }

  .chat-wrapper {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg);
  }

  @media (max-width: 760px) {
    .container {
      flex-direction: column;
    }

    .sidebar {
      height: auto;
      max-height: 34dvh;
      width: 100%;
      border-right: 0;
      border-bottom: 1px solid var(--border);
      padding: 0.75rem 1rem;
    }

    .chat-tabs {
      flex-direction: row;
      overflow-x: auto;
      overflow-y: hidden;
    }

    .chat-shell {
      height: 66dvh;
    }

    .chat-tabs .chat-tab {
      width: auto;
      max-width: 180px;
      flex-shrink: 0;
    }

    .chat-tab-wrapper {
      grid-template-columns: minmax(120px, 180px) 2rem;
      flex-shrink: 0;
    }

    .chat-tab {
      max-width: 180px;
    }
  }
</style>
