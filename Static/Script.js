document.addEventListener('DOMContentLoaded', () => {
  const fillEl = document.getElementById('meterFill');
  const panel = document.getElementById('meter-panel');

  if (!fillEl || !panel) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        fillEl.style.width = '92%';
        observer.disconnect();
      }
    });
  }, { threshold: 0.4 });

  observer.observe(panel);
});