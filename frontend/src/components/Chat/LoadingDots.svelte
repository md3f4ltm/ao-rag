<script>
  export let label = "A processar";
</script>

<div class="loading" role="status" aria-live="polite">
  <span class="sr-only">{label}</span>
  <span aria-hidden="true">{label}</span>
  <div class="dots-container" aria-hidden="true">
    <div class="dot"></div>
    <div class="dot"></div>
    <div class="dot"></div>
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

  .loading {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .dots-container {
    display: flex;
    gap: 4px;
    align-items: center;
    height: 100%;
  }

  .dot {
    width: 6px;
    height: 6px;
    background-color: currentColor;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
  }

  .dot:nth-child(1) { animation-delay: -0.32s; }
  .dot:nth-child(2) { animation-delay: -0.16s; }

  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0); opacity: 0.3;}
    40% { transform: scale(1); opacity: 1;}
  }
</style>
