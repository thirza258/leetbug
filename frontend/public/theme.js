// Apply a saved preference before rendering the application.
try {
  document.documentElement.dataset.theme = localStorage.getItem('leetbug.theme') === 'dark' ? 'dark' : 'light';
} catch {
  document.documentElement.dataset.theme = 'light';
}
