const CACHE="opencrochet-pro-m12-v5";
const SHELL=["/static/manifest.webmanifest","/static/icon-192.png","/static/icon-512.png","/static/apple-touch-icon.png"];
// true when this worker replaces an older one (an update), false on first install
let isUpdate=false;
self.addEventListener("install",e=>{isUpdate=!!self.registration.active;self.skipWaiting();e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));});
self.addEventListener("activate",e=>e.waitUntil(
 caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
 .then(()=>self.clients.claim())
 .then(()=>{
  // An installed PWA is resumed, not reloaded, when reopened, so an old page can
  // stay on screen indefinitely. On an update, reload windows that are in the
  // background (the user comes back to a fresh app) and ping visible ones so the
  // page can offer "Update now" instead of discarding work in progress.
  if(!isUpdate)return;
  return self.clients.matchAll({type:"window"}).then(cs=>Promise.all(cs.map(c=>{
   if(c.visibilityState==="visible"){try{c.postMessage({type:"ye-update"});}catch(_){ }return;}
   return c.navigate(c.url).catch(()=>{});
  })));
 })
));
self.addEventListener("fetch",e=>{
 if(e.request.method!=="GET")return;
 const u=new URL(e.request.url);
 if(u.pathname.startsWith("/api/"))return;
 e.respondWith(fetch(e.request).then(r=>{const x=r.clone();caches.open(CACHE).then(c=>c.put(e.request,x));return r}).catch(()=>caches.match(e.request)));
});
