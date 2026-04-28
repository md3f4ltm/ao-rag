<script>
  export let title = "SeismoGPT";
  export let subtitle = "Consulte dados sísmicos usando linguagem natural";
</script>

<header class="header">
  <h1 aria-label={title}>{title}</h1>
  <p class="subtitle">{subtitle}</p>
</header>

<style>
  .header {
    text-align: center;
    margin-bottom: 2rem;
  }

  h1 {
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 700;
    background: linear-gradient(to right, #3b82f6, #10b981);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
  }

  p.subtitle {
    color: #94a3b8;
    font-size: clamp(0.9rem, 2vw, 1.1rem);
    margin: 0;
  }
</style>
