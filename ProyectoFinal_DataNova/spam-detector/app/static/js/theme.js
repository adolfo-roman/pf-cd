/* static/js/theme.js */
// Theme toggling functionality
function initTheme() {
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
  } else {
    document.documentElement.classList.remove('dark');
    document.documentElement.classList.add('light');
  }
}

function toggleTheme() {
  if (document.documentElement.classList.contains('dark')) {
    document.documentElement.classList.remove('dark');
    document.documentElement.classList.add('light');
    localStorage.setItem('theme', 'light');
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: 'light' } }));
  } else {
    document.documentElement.classList.add('dark');
    document.documentElement.classList.remove('light');
    localStorage.setItem('theme', 'dark');
    window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: 'dark' } }));
  }
}

// Initialize theme on load
initTheme();

// expose functions to window (defensive)
window.toggleTheme = toggleTheme;
window.initTheme = initTheme;