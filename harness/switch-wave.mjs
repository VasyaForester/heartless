#!/usr/bin/env node
// Switch the board wave in one atomic CDP sequence.
// Usage: node harness/switch-wave.mjs --wave "Wave 3"
import {assertRuntime, CdpPage, listTargets} from './engine/cdp.mjs';
import {BOARD_MATCH} from './engine/board.mjs';
assertRuntime();
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const k = process.argv[i];
  if (!k.startsWith('--') || !process.argv[i + 1]) throw new Error('Expected --key value pairs.');
  args[k.slice(2)] = process.argv[i + 1];
}
const want = args.wave || 'Wave 3';
const cdpUrl = args.cdp || 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
const t = targets.find(x => x.type === 'page' && String(x.url || '').includes(BOARD_MATCH))
  || targets.find(x => x.type === 'page' && String(x.url || '').includes('grayswan.ai'));
if (!t) { console.log(JSON.stringify({error: 'no grayswan tab'})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 10000).connect();
await page.send('Page.enable');
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function clickRect(rect) {
  await page.send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: rect.x, y: rect.y});
  await page.send('Input.dispatchMouseEvent', {type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1});
  await page.send('Input.dispatchMouseEvent', {type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1});
}
// 1. open the wave trigger
const trig = await page.evaluate(`(() => { const b=document.querySelector('#bits-s1'); if(!b) return null; const r=b.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
if (!trig) { console.log(JSON.stringify({error: 'no trigger'})); process.exit(1); }
await clickRect(trig);
await sleep(700);
// React popovers may ignore synthetic mouse events — fall back to a JS click when no cards appeared.
let cardCount = await page.evaluate(`document.querySelectorAll('[data-testid^="wave-card"]').length`);
if (!cardCount) {
  await page.evaluate(`(() => { const b=document.querySelector('#bits-s1'); if(b) b.click(); })()`);
  await sleep(900);
  cardCount = await page.evaluate(`document.querySelectorAll('[data-testid^="wave-card"]').length`);
}
// 2. find the requested wave card
const card = await page.evaluate(`(() => {
  const cards=[...document.querySelectorAll('[data-testid^="wave-card"]')];
  const c=cards.find(el=>((el.textContent||'').includes(${JSON.stringify(want)})));
  if(!c) return {error:'card not found', have: cards.map(x=>(x.textContent||'').slice(0,40))};
  c.scrollIntoView({block:'center'});
  const r=c.getBoundingClientRect();
  return {x:r.x+r.width/2,y:r.y+r.height/2,text:(c.textContent||'').replace(/\\n/g,' ').slice(0,60)};
})()`);
if (card.error) { console.log(JSON.stringify(card)); page.close(); process.exit(1); }
await clickRect(card);
await sleep(1200);
// verify the switch actually took; JS-click the card as fallback
let nowWave = await page.evaluate(`(() => { const b=document.querySelector('#bits-s1'); return b ? (b.textContent||'') : ''; })()`);
if (!String(nowWave).includes(want)) {
  await page.evaluate(`(() => { const cards=[...document.querySelectorAll('[data-testid^="wave-card"]')]; const c=cards.find(el=>((el.textContent||'').includes(${JSON.stringify(want)}))); if(c) c.click(); })()`);
  await sleep(2200);
}
await sleep(1300);
const out = await page.evaluate(`(() => ({url: location.href, scenarios:[...document.querySelectorAll('button[data-behavior-id]')].map(b=>({id:b.getAttribute('data-behavior-id'), text:(b.textContent||'').replace(/\\s+/g,' ').trim().slice(0,140)}))}))()`);
// attach each card's track label (nearest preceding CHAT/AGENT/IMAGE/INDIRECT leaf)
const tracks = await page.evaluate(`(() => {
  const all=[...document.querySelectorAll('*')];
  const labels=all.map((x,i)=>({i,t:(x.childElementCount===0?(x.textContent||''):'').trim()})).filter(o=>/^(CHAT|AGENT|IMAGE|INDIRECT)$/.test(o.t));
  const out={};
  for(const b of document.querySelectorAll('button[data-behavior-id]')){
    const bi=all.indexOf(b); let best=null,bd=Infinity;
    for(const o of labels){ if(o.i<bi&&bi-o.i<bd){bd=bi-o.i;best=o.t;} }
    out[b.getAttribute('data-behavior-id')]=best;
  }
  return out;
})()`);
for (const s of out.scenarios) s.track = tracks[s.id] || null;
console.log(JSON.stringify({ok: true, card: card.text, url: out.url, scenarios: out.scenarios}));
page.close();
process.exit(0);
