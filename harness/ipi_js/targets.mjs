#!/usr/bin/env node
import {CdpPage, listTargets} from '../engine/cdp.mjs';
const cdpUrl = 'http://127.0.0.1:9223';
const targets = await listTargets(cdpUrl);
console.log('ALL TARGETS:');
for (const t of targets) console.log(t.type, '|', t.id.slice(0,10), '|', String(t.url).slice(0,120), '|', t.title);
