#!/usr/bin/env node
// new-chat.mjs — открывает СВЕЖИЙ чат арены через кнопку NEW (реальный user gesture → попап не блокируется).
// Печатает JSON {ok, newTabId, newUrl}. Использовать: CHAT_TARGET=<newTabId> для последующих шагов.
// Usage: node harness/new-chat.mjs [--cdp http://127.0.0.1:9223] [--target <tabId>]
import {assertRuntime, CdpPage, listTargets} from './engine/cdp.mjs';
assertRuntime();
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const k = process.argv[i];
  if (!k.startsWith('--') || !process.argv[i + 1]) throw new Error('Expected --key value pairs.');
  args[k.slice(2)] = process.argv[i + 1];
}
const cdpUrl = args.cdp || 'http://127.0.0.1:9223';
const board = 'https://app.grayswan.ai/arena/challenge/lucky-break-payday';

const pre = await listTargets(cdpUrl);
const preIds = new Set(pre.map(t => t.id));
const t = (args.target && pre.find(x => x.id === args.target))
  || pre.find(x => x.type === 'page' && String(x.url || '').includes('lucky-break-payday'));
if (!t) { console.log(JSON.stringify({error: 'no lucky-break tab'})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 15000).connect();
await page.send('Page.enable');

// 1) открыть модалку чатов: сперва корень борда, затем РЕАЛЬНЫЙ клик по SUBMISSIONS (надёжнее, чем ?modal=chats)
const url = await page.evaluate('location.href');
if (!String(url).includes('modal=chats')) {
  await page.evaluate(`(location.href = ${JSON.stringify(board + '?nav=')} + Date.now(), 'nav')`);
  await new Promise(r => setTimeout(r, 6500));
}
const subRect = await page.evaluate(`(() => {
  const b = [...document.querySelectorAll('button')].find(x => /^SUBMISSIONS/i.test((x.innerText||'').trim()));
  if (!b) return null;
  b.scrollIntoView({block: 'center'});
  const r = b.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2};
})()`);
if (subRect) {
  await page.send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: subRect.x, y: subRect.y});
  await page.send('Input.dispatchMouseEvent', {type: 'mousePressed', x: subRect.x, y: subRect.y, button: 'left', clickCount: 1});
  await page.send('Input.dispatchMouseEvent', {type: 'mouseReleased', x: subRect.x, y: subRect.y, button: 'left', clickCount: 1});
  await new Promise(r => setTimeout(r, 3000));
}
// 1b) перейти на вкладку CHATS внутри модалки (кнопка NEW живёт там)
const chatsTab = await page.evaluate(`(() => {
  const b = [...document.querySelectorAll('button,[role="tab"],a')].find(x => /^CHATS\\b/i.test((x.innerText||'').trim()));
  if (!b) return null;
  b.scrollIntoView({block: 'center'});
  const r = b.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2, text: (b.innerText||'').trim().slice(0, 30)};
})()`);
if (chatsTab) {
  await page.send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: chatsTab.x, y: chatsTab.y});
  await page.send('Input.dispatchMouseEvent', {type: 'mousePressed', x: chatsTab.x, y: chatsTab.y, button: 'left', clickCount: 1});
  await page.send('Input.dispatchMouseEvent', {type: 'mouseReleased', x: chatsTab.x, y: chatsTab.y, button: 'left', clickCount: 1});
  await new Promise(r => setTimeout(r, 2500));
}
// 2) найти кнопку NEW и её координаты
const rect = await page.evaluate(`(() => {
  const b = [...document.querySelectorAll('button,a,[role="button"]')].find(x => /^NEW\\b/i.test((x.innerText||'').trim()));
  if (!b) return null;
  b.scrollIntoView({block: 'center'});
  const r = b.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2, text: (b.innerText||'').trim().slice(0, 40)};
})()`);
if (!rect) { console.log(JSON.stringify({error: 'NEW button not found', subClicked: !!subRect})); page.close(); process.exit(1); }
// 3) РЕАЛЬНЫЙ клик (Input events = user gesture)
await page.send('Input.dispatchMouseEvent', {type: 'mouseMoved', x: rect.x, y: rect.y});
await page.send('Input.dispatchMouseEvent', {type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1});
await page.send('Input.dispatchMouseEvent', {type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1});
await new Promise(r => setTimeout(r, 4000));
// 4) найти новую вкладку
const post = await listTargets(cdpUrl);
const fresh = post.filter(x => x.type === 'page' && String(x.url || '').includes('lucky-break-payday') && !preIds.has(x.id));
console.log(JSON.stringify({
  ok: fresh.length > 0,
  clicked: rect.text,
  newTabId: fresh.length ? fresh[fresh.length - 1].id : null,
  newUrl: fresh.length ? fresh[fresh.length - 1].url : null,
  tabs: post.filter(x => x.type === 'page' && String(x.url || '').includes('grayswan')).map(x => ({id: x.id.slice(0, 10), url: String(x.url).slice(0, 90)}))
}));
page.close();
process.exit(0);
