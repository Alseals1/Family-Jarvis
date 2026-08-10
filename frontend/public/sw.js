const CACHE = 'jarvis-shell-v1';
const SHELL = ['/', '/index.html'];

self.addEventListener('install', e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL))));

self.addEventListener('fetch', e => {
  if (e.request.url.includes('/api/')) return; // network-only for API
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
