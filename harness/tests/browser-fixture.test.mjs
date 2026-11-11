// Real Chrome/Chromium + local-only neutral HTML, no account and no Arena requests.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {openTarget,connectPage} from '../engine/cdp.mjs';
import {context,inspect,expression} from '../engine/arena.mjs';
const run=promisify(execFile),sleep=ms=>new Promise(r=>setTimeout(r,ms));
const here=path.dirname(fileURLToPath(import.meta.url));const engine=fileURLToPath(new URL('../engine/arena.mjs',import.meta.url));
const chrome=process.env.CHROME_PATH||(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/usr/bin/google-chrome','/usr/bin/chromium','/usr/bin/chromium-browser'].find(fs.existsSync));
if(!chrome)throw new Error('Set CHROME_PATH to Chrome/Chromium for the real browser fixture.');
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'grayswan-neutral-fixture-'));const html=fs.readFileSync(path.join(here,'arena-fixture.html'));
const server=http.createServer((req,res)=>{res.writeHead(200,{'content-type':'text/html; charset=utf-8'});res.end(html);});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
const proc=spawn(chrome,['--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+path.join(dir,'browser'),'about:blank'],{stdio:['ignore','ignore','pipe']});let stderr='';proc.stderr.on('data',c=>stderr+=c);let page;
try{
  const portFile=path.join(dir,'browser','DevToolsActivePort');const deadline=Date.now()+15000;while(!fs.existsSync(portFile)&&Date.now()<deadline&&proc.exitCode===null)await sleep(100);if(!fs.existsSync(portFile))throw new Error('Chrome fixture did not start: '+stderr.slice(-1500));
  const cdpUrl='http://127.0.0.1:'+fs.readFileSync(portFile,'utf8').split('\n')[0];
  const tab=await openTarget({cdpUrl,origin,url:origin+'/arena/challenge/proving-ground'});await sleep(400);({page}=await connectPage({cdpUrl,origin,targetId:tab.id,timeoutMs:5000}));
  let snap=await inspect(page);assert.equal(snap.model.value,'Local Fixture Model');assert.equal(snap.judge.status,'unknown');assert.equal(snap.scenario.id,'neutral-local');assert.equal(snap.controls.find(x=>x.id==='selectedModel').value,'Local Fixture Model');assert.notEqual(snap.model.value,'Placeholder is not the model');
  await page.evaluate(expression({action:'show-criteria'}));snap=await context(page);assert(snap.criteria.some(x=>x.text.includes('neutral local fixture text')));
  await page.evaluate(`document.querySelector('#scenario').removeAttribute('data-behavior-switch');document.querySelector('#scenario').removeAttribute('data-behavior-id');document.querySelector('#selectedModel').removeAttribute('aria-label');document.querySelector('#selectedModel').removeAttribute('role');document.querySelector('#selectedModel').id='selection';true`);
  snap=await context(page);assert.equal(snap.scenario.id,null);assert.equal(snap.scenario.key,'title:1. Neutral local fixture');
  const base=['--cdp',cdpUrl,'--origin',origin];const cli=async(args)=>JSON.parse((await run(process.execPath,[engine,...args,...base],{timeout:15000,maxBuffer:1024*1024})).stdout);
  const modelList=await cli(['models','--target',tab.id]);assert.equal(modelList.snapshot.model.value,'Local Fixture Model');assert(modelList.snapshot.availableModels.some(x=>x.name==='Unavailable Fixture Model'&&x.disabled));
  await cli(['select-model','--target',tab.id,'--value','Second Fixture Model']);assert.equal((await context(page)).model.value,'Second Fixture Model');
  await cli(['select-model','--target',tab.id,'--value','Local Fixture Model']);assert.equal((await context(page)).model.value,'Local Fixture Model');
  const scope=path.join(dir,'scope.json'),events=path.join(dir,'events.jsonl'),prompt=path.join(dir,'prompt.txt');fs.writeFileSync(prompt,'Please produce neutral local fixture text.');
  await cli(['bind-scope','--target',tab.id,'--board','Proving Ground','--track','Chat','--scenario-id','neutral-local','--model-id','Local Fixture Model','--observed-context','Local training fixture selected by the user','--evidence-source','user-scenario','--out',scope]);
  const sent=await cli(['send','--scope',scope,'--file',prompt,'--operation-id','local-chat-1','--event-log',events,'--timeout-ms','5000']);assert.equal(sent.status,'observed');assert.equal(sent.response.text.length,18026);assert.equal((await page.evaluate('fixture')).sendClicks,1);
  await assert.rejects(()=>cli(['send','--scope',scope,'--file',prompt,'--operation-id','local-chat-1','--event-log',events,'--timeout-ms','5000']));assert.equal((await page.evaluate('fixture')).sendClicks,1);
  const judged=await cli(['judge','--scope',scope,'--operation-id','local-judge-1','--event-log',events,'--timeout-ms','5000']);assert.equal(judged.status,'accepted');assert.equal(judged.submissionId,'local-fixture-1');assert.equal((await page.evaluate('fixture')).judgeClicks,1);
  const records=fs.readFileSync(events,'utf8').trim().split('\n').map(JSON.parse);assert.equal(records.filter(x=>x.phase==='started').length,2);assert.equal(records.filter(x=>x.phase==='completed').length,2);
  console.log(JSON.stringify({status:'passed',arenaNetworkCalls:0,localBrowser:true,tests:['actual selected input value; placeholder ignored','Proving Ground accepted with explicit Training provenance','success text inside assistant message not a verdict','success criteria opened','nested settings accordion, plain model buttons, Closed status','actual aria-only criteria button and duplicate numbered scenario headings','full 18026-character assistant response','single send and duplicate operation refused','single judge with observed submission ID','two operation histories persisted']},null,2));
}finally{page?.close();proc.kill('SIGTERM');await new Promise(r=>server.close(r));await sleep(500);fs.rmSync(dir,{recursive:true,force:true});}
