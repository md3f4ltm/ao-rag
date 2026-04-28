<script>
  import { onMount } from 'svelte';
  import Header from './components/Layout/Header.svelte';
  import MessageList from './components/Chat/MessageList.svelte';
  import ChatInput from './components/Chat/ChatInput.svelte';

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

  let conversations = [createConversation()];
  let activeConversationId = conversations[0].id;
  let models = [];
  let selectedModel = '';
  let darkMode = false;
  let loading = false;
  let inputValue = '';
  let sidebarCollapsed = false;
  let topBarHidden = false;
  let showThoughts = true;

  $: activeConversation = conversations.find((chat) => chat.id === activeConversationId) || conversations[0];
  $: messages = activeConversation?.messages || [];

  onMount(async () => {
    document.body.dataset.theme = darkMode ? 'dark' : 'light';

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

  function updateConversation(id, updater) {
    conversations = conversations.map((chat) => (
      chat.id === id ? updater(chat) : chat
    ));
  }

  function updateActiveConversation(updater) {
    updateConversation(activeConversationId, updater);
  }

  function newConversation() {
    const chat = createConversation();
    conversations = [chat, ...conversations];
    activeConversationId = chat.id;
    inputValue = '';
  }

  function selectConversation(id) {
    if (loading) return;
    activeConversationId = id;
    inputValue = '';
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

  async function handleSendMessage(event) {
    const userMsg = event.detail.text;
    if (!userMsg) return;

    const targetConversationId = activeConversationId;
    const targetConversation = conversations.find((chat) => chat.id === targetConversationId);
    const botMessageId = crypto.randomUUID();

    const newTitle = targetConversation?.title === 'Novo chat' ? userMsg.slice(0, 42) : targetConversation?.title;
    updateConversation(targetConversationId, (chat) => ({
      ...chat,
      title: newTitle || chat.title,
      messages: [
        ...chat.messages,
        { role: 'user', text: userMsg },
        { id: botMessageId, role: 'bot', text: '', trace: [], traceDuration: 0, isLoading: true }
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
          model: selectedModel || undefined,
          client_time: new Date().toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
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

          const data = JSON.parse(line.slice(6));

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
              isError: isErrorResponse
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
        {#each conversations as chat}
          <button
            class:active={chat.id === activeConversationId}
            type="button"
            on:click={() => selectConversation(chat.id)}
          >
            {chat.title}
          </button>
        {/each}
      </div>
    {/if}
  </aside>

  <section class="chat-shell" aria-label="Interface de conversação">
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

  .chat-tabs button {
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

  .chat-tabs button:hover,
  .chat-tabs button.active {
    background: var(--hover-bg);
    color: var(--text);
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

    .chat-tabs button {
      width: auto;
      max-width: 180px;
      flex-shrink: 0;
    }
  }
</style>
