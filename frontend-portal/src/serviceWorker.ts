/**
 * Service Worker for PWA Support
 * Iteration 2: Offline capabilities
 */

const CACHE_NAME = "1c-ai-stack-v1";
const urlsToCache = [
  "/",
  "/index.html",
  "/assets/index.css",
  "/assets/index.js",
  "/manifest.json",
];

// Install event
self.addEventListener("install", (event: any) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener("fetch", (event: any) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      // Cache hit - return cached response
      if (response) {
        return response;
      }

      // Cache miss - fetch from network
      return fetch(event.request).then((response) => {
        // Don't cache non-successful responses
        if (!response || response.status !== 200 || response.type !== "basic") {
          return response;
        }

        // Clone response (can only be read once)
        const responseToCache = response.clone();

        // Cache for next time
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseToCache);
        });

        return response;
      });
    })
  );
});

// Activate event - clean up old caches
self.addEventListener("activate", (event: any) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Background sync (for offline actions)
self.addEventListener("sync", (event: any) => {
  if (event.tag === "sync-data") {
    event.waitUntil(syncData());
  }
});

async function syncData() {
  // Sync queued actions when back online
  const syncQueue = await getSyncQueue();

  for (const action of syncQueue) {
    try {
      await fetch(action.url, {
        method: action.method,
        body: JSON.stringify(action.data),
        headers: {
          "Content-Type": "application/json",
        },
      });

      // Remove from queue
      await removeFromSyncQueue(action.id);
    } catch (error) {
      console.error("Sync failed:", error);
    }
  }
}

async function getSyncQueue() {
  // TODO: Implement with IndexedDB
  return [];
}

async function removeFromSyncQueue(id: string) {
  // TODO: Implement
}

export {};
