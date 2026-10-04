// SahayID Service Worker for PWA installation & caching
const CACHE_NAME = 'sahayid-v1';
const ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/images/sahayid-logo.jpg',
  '/static/images/wave-bg.png',
  '/static/manifest.json'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch(() => {});
    })
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // Network first, fallback to cache for static resources
  if (e.request.method === 'GET' && e.request.url.includes('/static/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  }
});
