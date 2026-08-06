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

  event.waitUntil((async function() {
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

    const tag = data.type || 'alerte';
    let title = data.title;
    let body = data.body;
    let compteur = 1;

    /* Regroupement : si une notification du même type est déjà affichée et pas
       encore consultée, on combine au lieu de la remplacer silencieusement. */
    try {
      const existantes = await self.registration.getNotifications({ tag });
      if (existantes.length > 0) {
        const precedente = existantes[0];
        compteur = ((precedente.data && precedente.data.compteur) || 1) + 1;
        title = `${data.title} (${compteur})`;
        body = `${data.body}\n+ ${compteur - 1} alerte(s) précédente(s) non consultée(s)`;
      }
    } catch(e) {
      console.error('[SW] Erreur regroupement:', e);
    }

    /* Badge PWA : nombre de types d'alertes distincts actuellement non consultés
       (icône app — Chrome/Edge desktop + Android, sans effet sur iOS/Safari). */
    try {
      if ('setAppBadge' in self.navigator) {
        const toutes = await self.registration.getNotifications();
        self.navigator.setAppBadge(toutes.length + 1);
      }
    } catch(e) {
      console.error('[SW] Erreur badge:', e);
    }

    const options = {
      body: body,
      icon: data.icon || '/static/icon-192.png',
      badge: data.badge || '/static/icon-192.png',
      tag: tag,
      renotify: true,
      requireInteraction: data.type === 'danger',
      data: { url: data.url || '/', compteur: compteur },
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

    await self.registration.showNotification(title, options);
  })());
});

/* ── CLIC SUR NOTIFICATION ────────────────── */
self.addEventListener('notificationclick', function(event) {
  event.notification.close();

  /* L'utilisateur a consulté au moins une alerte → on vide le badge.
     Approximatif (ne distingue pas les autres alertes encore en attente),
     mais évite un badge qui reste bloqué après consultation. */
  if ('clearAppBadge' in self.navigator) {
    self.navigator.clearAppBadge().catch(function() {});
  }

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