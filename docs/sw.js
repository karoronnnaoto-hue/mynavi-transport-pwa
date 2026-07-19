const CACHE = "transport-search-v6";
const ASSETS = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "data/jobs.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(Promise.all([
    self.clients.claim(),
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  ]));
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    cache.put(request, response.clone());
    return response;
  } catch {
    return caches.match(request);
  }
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname.endsWith(".css") || url.pathname.endsWith(".js") || url.pathname.endsWith(".webmanifest") || url.pathname.endsWith("/data/jobs.json")) {
    event.respondWith(networkFirst(event.request));
    return;
  }
  event.respondWith(caches.match(event.request).then((response) => response || fetch(event.request)));
});
