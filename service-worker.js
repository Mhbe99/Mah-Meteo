const SW_VERSION = 'mah-meteo-v1';
const CACHE_NAME = SW_VERSION;

const CACHE_URLS = [
  '/',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

/* ── INSTALLATION ─────────────────────────── */
self.addEventListener('install', function(event) {
  console.log('[SW] Installation', SW_VERSION);
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(CACHE_URLS);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

/* ── ACTIVATION ───────────────────────────── */
self.addEventListener('activate', function(event) {
  console.log('[SW] Activation', SW_VERSION);
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) {
          return k !== CACHE_NAME;
        }).map(function(k) {
          console.log('[SW] Suppression ancien cache:', k);
          return caches.delete(k);
        })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

/* ── FETCH : réseau prioritaire ───────────── */
self.addEventListener('fetch', function(event) {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  /* API → jamais en cache */
  if (url.pathname.startsWith('/api/')) return;
  if (url.pathname.startsWith('/auth/')) return;

  event.respondWith(
    fetch(event.request).catch(function() {
      return caches.match(event.request);
    })
  );
});

/* ── NOTIFICATIONS PUSH ───────────────────── */
self.addEventListener('push', function(event) {
  console.log('[SW] Push reçu');

  let data = {
    title: 'Mah Météo',
    body: 'Nouvelle alerte',
    type: 'alerte',
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    url: '/'
  };

  try {
    if (event.data) {
      data = Object.assign(data, event.data.json());
    }
  } catch(e) {
    console.error('[SW] Erreur parsing push:', e);
  }

  /* Couleur badge selon type */
  const options = {
    body: data.body,
    icon: data.icon || '/static/icon-192.png',
    badge: data.badge || '/static/icon-192.png',
    tag: data.type || 'alerte',
    renotify: true,
    requireInteraction: data.type === 'danger',
    data: { url: data.url || '/' },
    actions: [
      {
        action: 'voir',
        title: 'Voir le dashboard'
      },
      {
        action: 'fermer',
        title: 'Fermer'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

/* ── CLIC SUR NOTIFICATION ────────────────── */
self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  if (event.action === 'fermer') return;

  const targetUrl = (event.notification.data &&
    event.notification.data.url)
    ? event.notification.data.url
    : '/';

  event.waitUntil(
    clients.matchAll({
      type: 'window',
      includeUncontrolled: true
    }).then(function(clientList) {
      /* Si app déjà ouverte → focus */
      for (let i = 0; i < clientList.length; i++) {
        const c = clientList[i];
        if (c.url.includes(self.location.origin)
            && 'focus' in c) {
          c.focus();
          c.postMessage({
            type: 'NAVIGATE',
            url: targetUrl
          });
          return;
        }
      }
      /* Sinon ouvrir une nouvelle fenêtre */
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

/* ── MESSAGE DEPUIS LE FRONTEND ───────────── */
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});