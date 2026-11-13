#!/usr/bin/env node
// Evaluate a JS expression in the board tab (from the boards.py profile) and print the result.
// Usage: node harness/eval-page.mjs --js "document.title"   (or --jsfile path)
import fs from 'node:fs';
import {assertRuntime, CdpPage, listTargets} from './engine/cdp.mjs';
import {BOARD_MATCH} from './engine/board.mjs';
assertRuntime();
const args = {};
for (let i = 2; i < process.argv.length; i += 2) {
  const k = process.argv[i];
  if (!k.startsWith('--') || !process.argv[i + 1]) throw new Error('Expected --key value pairs.');
  args[k.slice(2)] = process.argv[i + 1];
}
const expr = args.jsfile ? fs.readFileSync(args.jsfile, 'utf8') : (args.js || 'document.title');
const cdpUrl = args.cdp || 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
const pages = targets.filter(x => x.type === 'page' && String(x.url || '').includes('grayswan.ai'));
let t = null;
if (args.target) {
  t = pages.find(x => x.id === args.target) || null;
  if (!t) { console.log(JSON.stringify({error: 'target not found among grayswan tabs', target: args.target, tabs: pages.map(p => ({id: p.id, url: p.url}))})); process.exit(1); }
} else if (args.match) {
  const m = pages.filter(x => String(x.url || '').includes(args.match));
  if (m.length !== 1) { console.log(JSON.stringify({error: 'match not unique', match: args.match, found: m.length, tabs: pages.map(p => ({id: p.id, url: p.url}))})); process.exit(1); }
  t = m[0];
} else {
  const pg = pages.filter(x => String(x.url || '').includes(BOARD_MATCH));
  if (pg.length === 1) t = pg[0];
  else if (pages.length === 1) t = pages[0];
  else { console.log(JSON.stringify({error: 'multiple grayswan tabs; pass --match or --target', tabs: pages.map(p => ({id: p.id, url: p.url}))})); process.exit(1); }
}
if (!t) { console.log(JSON.stringify({error: 'no grayswan tab'})); process.exit(1); }
const page = await new CdpPage(t.webSocketDebuggerUrl, 10000).connect();
await page.send('Page.enable');
const result = await page.evaluate(`(() => { try { return ${expr}; } catch (e) { return {__err: String(e)}; } })()`);
console.log(typeof result === 'string' ? result : JSON.stringify(result, null, 1));
page.close();
process.exit(0);
