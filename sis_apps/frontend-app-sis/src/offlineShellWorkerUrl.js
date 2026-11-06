// Webpack emits the public worker as a separate same-origin asset, not as application code.
export default new URL('../public/offline-shell.js', import.meta.url);
