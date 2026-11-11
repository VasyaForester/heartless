import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {expression,click,fill,read,upload,wait,validateScope,validateObservedContext,waitResponse,waitJudge} from '../engine/arena.mjs';
import {selectTarget,matchingTargets,loopbackUrl,CdpPage,openTarget} from '../engine/cdp.mjs';

function fixture() {
  class Input {constructor(){this._value='';}get value(){return this._value;}set value(v){this._value=v;}}
  class Textarea extends Input {get value(){return this._value;}set value(v){this._value=v;}}
  const controls={};let clicks=0;let events=[];
  const element=(tag='BUTTON',text='Go')=>Object.assign(tag==='TEXTAREA'?new Textarea():new Input(),{
    tagName:tag,id:'fixture',type:tag==='INPUT'?'text':'',innerText:text,textContent:text,disabled:false,multiple:false,accept:'',isContentEditable:false,
    getAttribute(n){return ({type:this.type,id:this.id})[n]??null;},getBoundingClientRect(){return {width:100,height:30};},
    click(){clicks++;},dispatchEvent(e){events.push(e.type);return true;}
  });
  controls['#send']=[element()];controls['#input']=[element('TEXTAREA','')];controls['#response']=[element('ARTICLE','R'.repeat(14000))];
  controls['#duplicate']=[element(),element()];controls['#password']=[element('INPUT','')];controls['#password'][0].type='password';
  controls['#upload']=[element('INPUT','')];controls['#upload'][0].type='file';controls['#upload'][0].getBoundingClientRect=()=>({width:0,height:0});
  const context={CSS:{escape:s=>s},document:{title:'Offline fixture',querySelectorAll:s=>controls[s]||[]},location:{href:'http://127.0.0.1:9999/arena/demo',origin:'http://127.0.0.1:9999'},getComputedStyle:()=>({visibility:'visible',display:'block'}),HTMLInputElement:Input,HTMLTextAreaElement:Textarea,Event:class {constructor(type,opts){this.type=type;this.bubbles=opts.bubbles;}}};
  const sent=[];
  const page={evaluate:async e=>vm.runInNewContext(e,context),send:async(method,params)=>{sent.push({method,params});if(method==='DOM.getDocument')return {root:{nodeId:1}};if(method==='DOM.querySelectorAll')return {nodeIds:[7]};return {};}};
  return {page,controls,sent,get clicks(){return clicks;},get events(){return events;}};
}
export async function runSelfTests() {
  const passed=[];const check=async(name,fn)=>{await fn();passed.push(name);};
  await check('exact origin rejects lookalike host; ambiguous tabs require target',()=>{
    const rows=[{type:'page',id:'ok',url:'https://app.grayswan.ai/arena/a'},{type:'page',id:'evil',url:'https://app.grayswan.ai.evil.example/arena/a'}];
    assert.equal(matchingTargets(rows,'https://app.grayswan.ai').length,1);
    assert.equal(selectTarget(rows,'https://app.grayswan.ai').id,'ok');
    assert.throws(()=>selectTarget([...rows,{...rows[0],id:'two'}],'https://app.grayswan.ai'));
    assert.throws(()=>loopbackUrl('http://192.0.2.1:9223'));
  });
  await check('click performs exactly one action and no keyboard fallback',async()=>{const f=fixture();await click(f.page,'#send');assert.equal(f.clicks,1);assert.equal(f.events.length,0);});
  await check('ambiguous selector fails without clicking',async()=>{const f=fixture();await assert.rejects(()=>click(f.page,'#duplicate'));assert.equal(f.clicks,0);});
  await check('fill handles multiline text, emits input/change, never sends',async()=>{const f=fixture();const text='neutral\nfixture';await fill(f.page,'#input',text);assert.equal(f.controls['#input'][0].value,text);assert.deepEqual(f.events,['input','change']);assert.equal(f.clicks,0);await assert.rejects(()=>fill(f.page,'#password','x'));});
  await check('full response retains >14000 characters without fallback',async()=>{const f=fixture();const r=await read(f.page,'#response');assert.equal(r.matches[0].text.length,14000);const empty=await read(f.page,'#missing');assert.equal(empty.matches.length,0);});
  await check('hidden file upload uses actual CDP file API exactly once',async()=>{const f=fixture();const dir=fs.mkdtempSync(path.join(path.dirname(fileURLToPath(import.meta.url)),'.upload-fixture-'));try{const file=path.join(dir,'neutral.txt');fs.writeFileSync(file,'fixture');await upload(f.page,'#upload',[file]);assert.equal(f.sent.filter(x=>x.method==='DOM.setFileInputFiles').length,1);assert.deepEqual(f.sent.at(-1).params.files,[file]);}finally{fs.rmSync(dir,{recursive:true,force:true});}});
  await check('scope supports Training scenario /arena paths and rejects stale tab',()=>{const target={id:'a',url:'https://app.grayswan.ai/arena/scenario'};const scope={board:'Training',track:'Indirect',scenarioId:'s',modelId:'m',observedContext:'Training navigation observed',evidenceSource:'training-link',targetId:'a',origin:'https://app.grayswan.ai',url:target.url};assert.equal(validateScope(scope,target,scope.origin),scope);assert.throws(()=>validateScope(scope,{...target,url:target.url+'/new'},scope.origin));assert.equal(validateScope({...scope,board:'Proving Ground'},target,scope.origin).board,'Proving Ground');assert.throws(()=>validateScope({...scope,evidenceSource:null},target,scope.origin));});
  await check('wait timeout is pending, not a failed judge',async()=>{const f=fixture();const r=await wait(f.page,'#missing',{timeoutMs:1,condition:'visible'});assert.equal(r.met,false);assert.equal(r.status,'pending');const done=await wait(f.page,'#response',{timeoutMs:1,condition:'visible'});assert.equal(done.met,true);});
  await check('CDP timed-out requests are removed and no action retried',async()=>{
    const Original=globalThis.WebSocket;let methods=[];
    class Socket extends EventTarget {static OPEN=1;constructor(){super();this.readyState=1;queueMicrotask(()=>this.dispatchEvent(new Event('open')));}send(raw){const m=JSON.parse(raw);methods.push(m.method);if(m.method==='Never.respond')return;queueMicrotask(()=>this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({id:m.id,result:{}})})));}close(){this.readyState=3;this.dispatchEvent(new Event('close'));}}
    globalThis.WebSocket=Socket;
    try{const p=await new CdpPage('ws://127.0.0.1:9223/devtools/page/fixture',10).connect();await assert.rejects(()=>p.send('Never.respond'));assert.equal(p.pending.size,0);assert.equal(methods.filter(x=>x==='Never.respond').length,1);p.close();}finally{globalThis.WebSocket=Original;}
  });
  await check('open without Arena target creates one tab; exact existing URL reuses it',async()=>{
    const original=globalThis.fetch;let writes=0;const targets=[];
    globalThis.fetch=async(url,opts={})=>({ok:true,json:async()=>{if(String(url).includes('/json/list'))return targets;if(opts.method==='PUT'){writes++;return {id:'created'};}throw new Error('Unexpected request');}});
    try{const options={cdpUrl:'http://127.0.0.1:9223',origin:'https://app.grayswan.ai',url:'https://app.grayswan.ai/training'};assert.equal((await openTarget(options)).id,'created');assert.equal(writes,1);targets.push({id:'existing',type:'page',url:options.url});assert.equal((await openTarget(options)).id,'existing');assert.equal(writes,1);await assert.rejects(()=>openTarget({...options,url:'https://example.com'}));}finally{globalThis.fetch=original;}
  });
  await check('model/scenario changes invalidate bound scope',()=>{const scope={url:'https://app.grayswan.ai/arena/a',modelId:'Actual Model',scenarioId:'scenario-a'};const snap={url:scope.url,model:{value:'Actual Model'},scenario:{id:'scenario-a'}};validateObservedContext(scope,snap);assert.throws(()=>validateObservedContext(scope,{...snap,model:{value:null,status:'unknown'}}));assert.throws(()=>validateObservedContext(scope,{...snap,scenario:{id:'scenario-b'}}));});
  await check('response wait rejects old assistant text and retains full fresh response',async()=>{
    const old={assistantMessages:[{role:'assistant',text:'previous'}],messages:[],streaming:false};let r=await waitResponse({evaluate:async()=>old},old,{timeoutMs:1,stableMs:0});assert.equal(r.status,'pending');const fresh={...old,assistantMessages:[...old.assistantMessages,{role:'assistant',text:'N'.repeat(18000)}],messages:[]};r=await waitResponse({evaluate:async()=>fresh},old,{timeoutMs:1,stableMs:0});assert.equal(r.status,'observed');assert.equal(r.response.text.length,18000);
  });
  await check('judge wait never reuses an old success or fabricates timeout verdict',async()=>{
    const old={judge:{status:'accepted',submissionId:'old',evidence:[{text:'Break Successful!'}]}};let r=await waitJudge({evaluate:async()=>old},old,{timeoutMs:1});assert.equal(r.status,'pending');const fresh={judge:{status:'rejected',submissionId:'new',evidence:[{text:'Break Rejected'}]}};r=await waitJudge({evaluate:async()=>fresh},old,{timeoutMs:1});assert.equal(r.status,'rejected');
  });
  console.log(JSON.stringify({status:'passed',offline:true,networkCalls:0,tests:passed},null,2));
}
