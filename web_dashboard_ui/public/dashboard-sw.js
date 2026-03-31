self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }

  const title = payload.title || 'Monitoring Alert';
  const body = payload.body || 'A new event was detected.';
  const url = payload.url || '/dashboard/remote/mobile';
  const tag = payload.tag || 'thesis-monitor-alert';

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      data: payload.data || { url },
      badge: '/dashboard/icon.svg',
      icon: '/dashboard/icon.svg',
      renotify: true,
      requireInteraction: false,
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  const url = data.url || '/dashboard/remote/mobile';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes('/dashboard') && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});
