// SahayID Service Worker for PWA installation & reliable offline asset caching
const CACHE_NAME = 'sahayid-v4';
const ASSETS = [
  '/',
  '/manifest.json',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/images/sahayid-logo.jpg',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/images/apple-touch-icon.png',
  '/static/images/favicon.png'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch((err) => {
        console.log('[SahayID SW] Cache asset load note:', err);
      });
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
  if (e.request.method !== 'GET') return;

  // Static assets network-first with cache fallback
  if (e.request.url.includes('/static/') || e.request.url.includes('/manifest.json')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  }
});
