#!/usr/bin/env node
// Click a chat-list row in the Arena chats modal by matching its text (e.g. a model name).
// Usage: node harness/click-chat-row.mjs --text "Sand Elephant Giga" [--cdp http://127.0.0.1:9223]
import {assertRuntime, CdpPage, listTargets} from './engine/cdp.mjs';
import {BOARD_MATCH} from './engine/board.mjs';
assertRuntime();
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const k = process.argv[i];
  if (!k.startsWith('--') || !process.argv[i + 1]) throw new Error('Expected --key value pairs.');
  args[k.slice(2)] = process.argv[i + 1];
}
const cdpUrl = args.cdp || 'http://127.0.0.1:9223';
const needle = args.text || '';
const targets = await listTargets(cdpUrl);
const t = targets.find(x => x.type === 'page' && String(x.url || '').includes(BOARD_MATCH))
  || targets.find(x => x.type === 'page' && String(x.url || '').includes('grayswan.ai'));
if (!t) { console.log(JSON.stringify({error: 'no grayswan tab', tabs: targets.map(x => x.url).slice(0, 5)})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 10000).connect();
await page.send('Page.enable');
const also = args.also || '';
const rect = await page.evaluate(`(() => {
  const anchors = [...document.querySelectorAll('a,button,[role="tab"]')];
  const needleL = ${JSON.stringify(needle)}.toLowerCase();
  const alsoL = ${JSON.stringify(also)}.toLowerCase();
  const a = anchors.find(el => ((el.textContent || '').toLowerCase()).includes(needleL) && ((el.textContent || '').toLowerCase()).includes(alsoL));
  if (!a) return null;
  a.scrollIntoView({block: 'center'});
  const r = a.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height, text: (a.textContent || '').slice(0, 120)};
})()`);
if (!rect) { console.log(JSON.stringify({error: 'row not found', needle})); page.close(); process.exit(1); }
await page.send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: rect.x, y: rect.y});
await page.send('Input.dispatchMouseEvent', {type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1});
await page.send('Input.dispatchMouseEvent', {type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1});
await new Promise(r => setTimeout(r, 1800));
const url = await page.evaluate('location.href');
console.log(JSON.stringify({ok: true, clicked: rect.text, rect: {x: Math.round(rect.x), y: Math.round(rect.y)}, url}));
page.close();
process.exit(0);
