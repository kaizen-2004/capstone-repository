const DEVICE_ID_KEY = 'thesis_mobile_device_id_v1';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index);
  }
  return outputArray;
}

export function getOrCreateMobileDeviceId(): string {
  const existing = window.localStorage.getItem(DEVICE_ID_KEY);
  if (existing && existing.length >= 8) {
    return existing;
  }
  const generated = `mobile-${crypto.randomUUID()}`;
  window.localStorage.setItem(DEVICE_ID_KEY, generated);
  return generated;
}

export function isPushSupported(): boolean {
  return Boolean(
    typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window,
  );
}

export async function registerDashboardServiceWorker(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.register('/dashboard/sw.js', { scope: '/dashboard/' });
}

export async function ensurePushSubscription(
  vapidPublicKey: string,
): Promise<PushSubscription | null> {
  if (!isPushSupported()) {
    return null;
  }

  if (Notification.permission === 'denied') {
    return null;
  }

  if (Notification.permission !== 'granted') {
    const result = await Notification.requestPermission();
    if (result !== 'granted') {
      return null;
    }
  }

  const registration = await registerDashboardServiceWorker();
  const current = await registration.pushManager.getSubscription();
  if (current) {
    return current;
  }
  if (!vapidPublicKey) {
    return null;
  }

  return registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  });
}

export async function disablePushSubscription(): Promise<boolean> {
  if (!isPushSupported()) {
    return false;
  }
  const registration = await registerDashboardServiceWorker();
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    return false;
  }
  return subscription.unsubscribe();
}
