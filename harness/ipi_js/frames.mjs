#!/usr/bin/env node
// Dump frame tree + evaluate text in the e2b world frame.
import {CdpPage, listTargets} from '../engine/cdp.mjs';

const cdpUrl = 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
const pages = targets.filter(x => x.type === 'page' && String(x.url || '').includes('grayswan.ai'));
const t = pages.find(x => String(x.url).includes('ipi-black-2026')) || pages[0];
const page = await new CdpPage(t.webSocketDebuggerUrl, 20000).connect();
await page.send('Page.enable');
const ft = await page.send('Page.getFrameTree');
const frames = [];
(function walk(n) {
  const f = n.frame;
  frames.push({id: f.id, url: f.url, name: f.name, securityOrigin: f.securityOrigin});
  (n.childFrames || []).forEach(walk);
})(ft.frameTree);
console.log(JSON.stringify(frames, null, 1));

const target = frames.find(f => String(f.url).includes('e2b.app'));
if (target) {
  try {
    const world = await page.send('Page.createIsolatedWorld', {frameId: target.id, worldName: 'ipi_probe'});
    const res = await page.send('Runtime.evaluate', {
      expression: 'document.body.innerText.slice(0,4000)',
      contextId: world.executionContextId,
      returnByValue: true,
    });
    console.log('---WORLD TEXT---');
    console.log(res.result?.value ?? JSON.stringify(res).slice(0,2000));
  } catch (e) {
    console.log('EVAL ERR', String(e).slice(0,500));
  }
}
page.close();
process.exit(0);
