/* Calories — offline app shell.
   Bump CACHE whenever this file, foods.json or anything in vendor/ changes,
   or installed phones keep the old copy. */
const CACHE = "calories-v1";
const PAGE = "./index.html";
const SHELL = [
  "./", PAGE, "./manifest.webmanifest", "./foods.json", "./vendor/zxing-0.21.3.min.js",
  "./apple-touch-icon.png", "./icon-192.png", "./icon-512.png", "./icon-512-maskable.png"
];
/* Big and only changed by bumping CACHE: served from cache, never re-fetched
   in the background (foods.json is half a megabyte over the wire). */
const FROZEN = ["foods.json", "vendor/"];
const NET_TIMEOUT = 2500;

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE)
      /* allSettled: one missing file must not block the whole install */
      .then(c => Promise.allSettled(SHELL.map(u => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const put = (key, res) => {
  if (!res || !res.ok || res.type !== "basic") return res;
  const copy = res.clone();
  caches.open(CACHE).then(c => c.put(key, copy));
  return res;
};
const fromCache = key => caches.open(CACHE).then(c => c.match(key, { ignoreSearch: true }));

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  /* Supabase and Open Food Facts go straight to the network. */
  if (url.origin !== self.location.origin) return;

  /* The page: network first, so a published update is live immediately, with
     the cached copy the moment the network fails or stalls. no-cache makes the
     browser revalidate instead of answering from its HTTP cache, which GitHub
     Pages allows for ten minutes; unchanged, that costs a 304. */
  if (req.mode === "navigate") {
    const net = fetch(req.url, { cache: "no-cache", credentials: "same-origin" })
      .then(res => put(PAGE, res)).catch(() => null);
    e.waitUntil(net);
    e.respondWith(
      Promise.race([net, new Promise(r => setTimeout(() => r(null), NET_TIMEOUT))])
        .then(res => res || fromCache(PAGE))
        .then(res => res || fetch(req))
    );
    return;
  }

  if (FROZEN.some(p => url.pathname.includes("/" + p) || url.pathname.endsWith(p))) {
    e.respondWith(fromCache(req).then(hit => hit || fetch(req).then(res => put(req, res))));
    return;
  }

  /* Icons and manifest: cache first, refreshed in the background.
     waitUntil keeps the worker alive long enough for the put to land. */
  const fresh = fetch(req).then(res => put(req, res)).catch(() => null);
  e.waitUntil(fresh);
  e.respondWith(fromCache(req).then(hit => hit || fresh).then(res => res || fetch(req)));
});
