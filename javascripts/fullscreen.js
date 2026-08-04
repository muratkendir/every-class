/* Adds a fullscreen toggle button to every mkdocs_puml diagram viewer.
   The button joins the plugin's own control bar (copy/download/zoom),
   which is injected into each .puml container on the same page event. */

(function () {
  const enterSvg = `
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-maximize">
<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>
</svg>`;

  const exitSvg = `
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-minimize">
<path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>
</svg>`;

  function wire(container) {
    if (container.querySelector('.puml-fullscreen')) return;
    const control = container.querySelector('.control');
    if (!control) return; // plugin controls not injected yet

    const btn = document.createElement('button');
    btn.className = 'icon-button puml-fullscreen';
    btn.title = 'Toggle fullscreen';
    btn.innerHTML = enterSvg;
    btn.addEventListener('click', () => {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        container.requestFullscreen();
      }
    });
    document.addEventListener('fullscreenchange', () => {
      btn.innerHTML = document.fullscreenElement === container ? exitSvg : enterSvg;
    });
    control.appendChild(btn);
  }

  function process() {
    const containers = document.querySelectorAll('.puml');
    containers.forEach(wire);
    // mkdocs_puml injects .control on the same event; retry for stragglers
    setTimeout(() => containers.forEach(wire), 100);
  }

  // mkdocs-material instant loading hook, plain load as fallback
  if (typeof document$ !== 'undefined' && document$.subscribe) {
    document$.subscribe(process);
  } else {
    document.addEventListener('DOMContentLoaded', process);
  }
})();
