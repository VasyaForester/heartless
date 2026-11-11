// Portable CDP transport. Adapted from the organizer's transport; no external npm packages.
export function assertRuntime() {
  if (Number(process.versions.node.split('.')[0]) < 22 || typeof WebSocket !== 'function') {
    throw new Error('Node.js 22+ with native WebSocket is required (https://nodejs.org/).');
  }
}
export function loopbackUrl(value, protocols = ['http:']) {
  const u = new URL(value);
  if (!protocols.includes(u.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(u.hostname)
      || u.username || u.password || u.search || u.hash) {
    throw new Error('CDP endpoint must be an unauthenticated loopback URL.');
  }
  return u;
}
export async function fetchJson(url, timeoutMs = 5000) {
  const r = await fetch(url, {signal: AbortSignal.timeout(timeoutMs), redirect: 'error'});
  if (!r.ok) throw new Error(`CDP HTTP ${r.status}`);
  return r.json();
}
export async function listTargets(cdpUrl) {
  const u = loopbackUrl(cdpUrl); u.pathname = '/json/list';
  const targets = await fetchJson(u);
  if (!Array.isArray(targets)) throw new Error('Invalid CDP target list.');
  return targets;
}
export function matchingTargets(targets, origin) {
  const expected = new URL(origin).origin;
  return targets.filter(t => {
    try { return t.type === 'page' && new URL(t.url).origin === expected; } catch { return false; }
  });
}
export function selectTarget(targets, origin, targetId) {
  const matches = matchingTargets(targets, origin);
  if (targetId) {
    const target = matches.find(t => t.id === targetId);
    if (!target) throw new Error('Target ID is absent or has a different origin. Inspect tabs again.');
    return target;
  }
  if (matches.length !== 1) throw new Error(`Expected one matching tab; found ${matches.length}. Supply --target ID.`);
  return matches[0];
}
export class CdpPage {
  constructor(webSocketDebuggerUrl, timeoutMs = 15000) {
    loopbackUrl(webSocketDebuggerUrl, ['ws:']);
    this.url = webSocketDebuggerUrl; this.timeoutMs = timeoutMs;
    this.socket = null; this.nextId = 1; this.pending = new Map();
  }
  async connect() {
    assertRuntime();
    this.socket = new WebSocket(this.url);
    this.socket.addEventListener('message', event => {
      let message;
      try { message = JSON.parse(String(event.data)); } catch { return; }
      const p = this.pending.get(message.id);
      if (!p) return;
      clearTimeout(p.timer); this.pending.delete(message.id);
      if (message.error) p.reject(new Error(message.error.message)); else p.resolve(message.result);
    });
    this.socket.addEventListener('close', () => this.rejectPending('CDP connection closed; reconcile before retrying an action.'));
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.socket.close(); reject(new Error('CDP connection timeout.')); }, this.timeoutMs);
      this.socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, {once:true});
      this.socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('Cannot connect to CDP.')); }, {once:true});
    });
    await this.send('Runtime.enable');
    return this;
  }
  rejectPending(message) {
    for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(new Error(message)); }
    this.pending.clear();
  }
  send(method, params = {}) {
    if (this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(new Error('CDP is not connected.'));
    const id = this.nextId++;
    return new Promise((resolve,reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`${method} timed out. Its outcome may be unknown; inspect before retrying.`));
      }, this.timeoutMs);
      this.pending.set(id, {resolve,reject,timer});
      try { this.socket.send(JSON.stringify({id,method,params})); }
      catch (error) { clearTimeout(timer); this.pending.delete(id); reject(error); }
    });
  }
  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', {expression, awaitPromise:true, returnByValue:true, userGesture:false});
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result?.value;
  }
  close() { this.rejectPending('CDP disconnected.'); this.socket?.close(); }
}
export async function connectPage({cdpUrl, origin, targetId, timeoutMs}) {
  const target = selectTarget(await listTargets(cdpUrl), origin, targetId);
  const page = await new CdpPage(target.webSocketDebuggerUrl, timeoutMs).connect();
  const location = await page.evaluate('({origin:location.origin,href:location.href})');
  if (location.origin !== new URL(origin).origin) { page.close(); throw new Error('Tab navigated to a different origin.'); }
  return {page,target};
}

// Open the requested Arena page without requiring an existing Arena target.
// A matching exact URL is reused; other tabs are preserved unless --target was explicit.
export async function openTarget({cdpUrl,origin,url,targetId,timeoutMs=15000}) {
  const destination=new URL(url);
  if(destination.origin!==new URL(origin).origin||destination.username||destination.password)throw new Error('Open URL must have the configured Arena origin.');
  const targets=await listTargets(cdpUrl);
  const existing=targetId?selectTarget(targets,origin,targetId):matchingTargets(targets,origin).find(t=>t.url===destination.href);
  if(existing){
    if(existing.url!==destination.href){const page=await new CdpPage(existing.webSocketDebuggerUrl,timeoutMs).connect();try{await page.send('Page.navigate',{url:destination.href});}finally{page.close();}}
    return {id:existing.id,url:destination.href,reused:true,navigated:existing.url!==destination.href,next:'Wait for page load, then inspect. If sign-in is shown, sign in to your own account in this browser.'};
  }
  const endpoint=loopbackUrl(cdpUrl);endpoint.pathname='/json/new';endpoint.search='?'+destination.href;
  const response=await fetch(endpoint,{method:'PUT',signal:AbortSignal.timeout(timeoutMs),redirect:'error'});
  if(!response.ok)throw new Error(`Cannot open browser tab: CDP HTTP ${response.status}. Check Chrome/Chromium debug browser.`);
  const created=await response.json();
  if(!created.id)throw new Error('CDP did not return a created page target.');
  return {id:created.id,url:destination.href,reused:false,navigated:false,next:'Wait for page load, then inspect. If sign-in is shown, sign in to your own account in this browser.'};
}
