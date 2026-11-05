/* Keep an embedded health portal session separate from standalone Xiaozhi login. */
const xiaozhiAuth = (() => {
 const params = new URLSearchParams(location.search)
 const embedded = window.parent !== window && params.get('embedded') === 'health'
 const portal = params.get('portal')
 const portalOrigin = ['http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8800', 'http://localhost:8800'].includes(portal) ? portal : null
 const storage = embedded ? sessionStorage : localStorage
 const key = embedded ? 'health-portal-token' : 'token'
 return {
  get: () => !embedded || portalOrigin ? storage.getItem(key) : null,
  set: token => storage.setItem(key, token),
  expire() {
   storage.removeItem(key)
   if (!embedded) location.replace('/static/login.html?v=20')
   else if (portalOrigin) window.parent.postMessage({type: 'employee-bridge-expired'}, portalOrigin)
  },
  url(path) {
   if (!embedded || !portalOrigin) return path
   const url = new URL(path, location.origin)
   url.searchParams.set('embedded', 'health')
   url.searchParams.set('portal', portalOrigin)
   return url.pathname + url.search + url.hash
  }
 }
})()
