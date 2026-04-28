<script>
  import Header from './components/Layout/Header.svelte';
  import MessageList from './components/Chat/MessageList.svelte';
  import ChatInput from './components/Chat/ChatInput.svelte';

  let messages = [
    {
      role: 'bot',
      text: `Olá! Sou o SeismoGPT. Podes perguntar-me sobre sismos, por exemplo:\n\n• "Qual foi o último sismo em Portugal?"\n• "Sismos com magnitude superior a 5 nos últimos 7 dias"\n• "Houve sismos perto dos Açores?"`,
      filters: null,
      isError: false
    }
  ];
  let loading = false;
  let inputValue = '';

  async function handleSendMessage(event) {
    const userMsg = event.detail.text;
    if (!userMsg) return;
    
    // Add user message
    messages = [...messages, { role: 'user', text: userMsg }];
    loading = true;
    
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg })
      });
      
      const data = await res.json();
      
      if (res.ok) {
        // Detect if response contains the error format from backend
        const isErrorResponse = data.response.includes('⚠️ **Erro**:') || data.response.includes('**Erro**:');
        
        messages = [...messages, { 
          role: 'bot', 
          text: data.response, 
          filters: data.filters_extracted,
          isError: isErrorResponse
        }];
      } else {
        messages = [...messages, { 
          role: 'bot', 
          text: 'Desculpe, ocorreu um erro ao comunicar com a API do servidor.',
          isError: true
        }];
      }
    } catch (error) {
      messages = [...messages, { 
        role: 'bot', 
        text: 'Não foi possível ligar ao servidor. Verifique a ligação.',
        isError: true
      }];
    } finally {
      loading = false;
    }
  }
</script>

<main class="container">
  <Header />

  <section class="chat-wrapper" aria-label="Interface de conversação">
    <MessageList {messages} {loading} />
    <ChatInput 
      bind:value={inputValue} 
      {loading} 
      on:submit={handleSendMessage} 
    />
  </section>
</main>

<style>
  .container {
    width: 100vw;
    max-width: 800px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    height: 100vh;
    padding: clamp(1rem, 3vw, 2rem);
  }

  .chat-wrapper {
    flex: 1;
    background: var(--card-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--card-border);
    border-radius: 24px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
  }
</style>
