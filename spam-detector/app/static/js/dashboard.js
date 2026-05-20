// dashboard.js
document.addEventListener('DOMContentLoaded', () => {
  // Animar barras semanales con IntersectionObserver
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.querySelectorAll('.bar-fill[data-target], .bar-fill-spam[data-target]').forEach((bar, i) => {
        const t = bar.dataset.target;
        setTimeout(() => { bar.style.width = t + '%'; }, i * 80);
      });
      observer.unobserve(entry.target);
    });
  }, { threshold: .1 });

  const chart = document.getElementById('weekly-chart');
  if (chart) observer.observe(chart);
});
