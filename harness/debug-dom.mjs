#!/usr/bin/env node
// Diagnostic: dump key DOM facts from the proving-ground tab.
import {assertRuntime, CdpPage, listTargets} from './engine/cdp.mjs';
assertRuntime();
const cdpUrl = 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
const pages = targets.filter(x => x.type === 'page');
console.log(JSON.stringify({pages: pages.map(p => p.url).slice(0, 8)}, null, 1));
const t = pages.find(x => String(x.url || '').includes('/arena/challenge/proving-ground'))
  || pages.find(x => String(x.url || '').includes('grayswan.ai'));
if (!t) { console.log(JSON.stringify({error: 'no target'})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 10000).connect();
await page.send('Page.enable');
const info = await page.evaluate(`(() => {
  const btns = [...document.querySelectorAll('a,button,[role="tab"]')];
  const chatsBtn = btns.find(el => (el.textContent || '').includes('CHATS'));
  const dialog = document.querySelector('[role="dialog"],[aria-modal="true"]');
  return {
    href: location.href,
    nButtons: btns.length,
    chatsBtnText: chatsBtn ? (chatsBtn.textContent || '').slice(0, 60) : null,
    dialogPresent: !!dialog,
    dialogText: dialog ? (dialog.textContent || '').slice(0, 160) : null,
  };
})()`);
console.log(JSON.stringify(info, null, 1));
page.close();
process.exit(0);
