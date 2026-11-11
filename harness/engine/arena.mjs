#!/usr/bin/env node
// Portable adaptation of the organizer's browser workflow. No stored attack prompts.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {assertRuntime,connectPage,listTargets,matchingTargets,openTarget} from './cdp.mjs';
const WORKSPACE=fileURLToPath(new URL('../../',import.meta.url));
const TRACKS=['Chat','Image','Agent','Indirect'];

// Serialized into the browser. Read the actual DOM, not URL-based assumptions.
export function domOperation(args) {
  const q=s=>[...document.querySelectorAll(s)];
  const norm=s=>String(s||'').replace(/\s+/g,' ').trim();
  const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none';};
  const attr=(e,n)=>e.getAttribute(n)||'';
  const text=e=>String(e.innerText??e.textContent??'').trim();
  const safeValue=e=>['INPUT','TEXTAREA','SELECT'].includes(e.tagName)&&!['password','hidden','file'].includes(e.type)?e.value:null;
  const selector=e=>{
    if(e.id)return '#'+CSS.escape(e.id);
    for(const a of ['data-testid','data-behavior-id','aria-label','name']){const v=attr(e,a);if(v){const s=e.tagName.toLowerCase()+'['+a+'='+JSON.stringify(v)+']';if(q(s).length===1)return s;}}
    const parts=[];let n=e;
    while(n&&n.nodeType===1&&parts.length<12){const tag=n.tagName.toLowerCase();const siblings=n.parentElement?[...n.parentElement.children].filter(x=>x.tagName===n.tagName):[n];parts.unshift(tag+':nth-of-type('+(siblings.indexOf(n)+1)+')');const s=parts.join(' > ');if(q(s).length===1)return s;n=n.parentElement;}
    return null;
  };
  const brief=e=>({tag:e.tagName.toLowerCase(),selector:selector(e),id:e.id||null,role:attr(e,'role')||null,type:attr(e,'type')||null,name:attr(e,'name')||null,ariaLabel:attr(e,'aria-label')||null,testId:attr(e,'data-testid')||null,placeholder:attr(e,'placeholder')||null,value:safeValue(e),text:text(e).slice(0,240),disabled:!!e.disabled||attr(e,'aria-disabled')==='true'});
  const enabled=e=>visible(e)&&!e.disabled&&attr(e,'aria-disabled')!=='true';
  const controls=()=>q('button,input,textarea,select,[contenteditable="true"],[role="button"],[role="textbox"],[role="combobox"],[role="option"],a[href]').filter(visible);
  const modelPicker=()=>{
    const explicit=q('[data-testid="challengeConfigPanelButton"],button[aria-label="Open challenge settings panel"]').filter(visible);
    if(explicit.length)return explicit;
    const buttons=q('button,[role="button"]').filter(visible).filter(e=>/^Attacking:/.test(norm(text(e)))||/^(Model|Models)$/i.test(norm(text(e)))||/^(select|choose|current|selected) model/i.test(attr(e,'aria-label')));
    if(buttons.length)return buttons;
    return q('[role="combobox"]').filter(visible).filter(e=>/model/i.test(attr(e,'aria-label')));
  };
  const modelName=e=>norm(text(e)).replace(/(?:\s+(?:BROKEN|Closed))+$/i,'').trim();
  const modelAccordion=()=>q('button,[role="button"]').filter(visible).filter(e=>/^Model\n[^\n]+/i.test(text(e)));
  const modelOptions=()=>{
    const lists=q('[role="listbox"][aria-label="Available models"],[data-testid="modelPicker"],[data-testid="model-picker"]').filter(visible);
    const es=lists.flatMap(e=>[...e.querySelectorAll('[role="option"],.model-card,button,li')]).filter(visible);
    const semantic=es.filter(e=>e.matches('[role="option"],.model-card'));const generic=es.filter(e=>!semantic.some(other=>other===e||other.contains(e)||e.contains(other))&&!es.some(child=>child!==e&&e.contains(child)&&modelName(child)===modelName(e)));return [...new Set([...semantic,...generic])];
  };
  const getContext=()=>{
    const all=controls();const candidates=[];
    const add=(e,value,source,confidence='confirmed')=>{value=norm(value).replace(/^Attacking:\s*/i,'');if(value&&!/^(model|models|select model|choose model|attacking)$/i.test(value))candidates.push({value,source,confidence,selector:selector(e)});};
    for(const e of modelAccordion()){const lines=text(e).split(/\n/).map(norm).filter(Boolean);if(lines[1])add(e,lines[1],'selected model in settings accordion');}
    for(const e of modelPicker()){const value=safeValue(e);if(value)add(e,value,'model control value');else if(/^Attacking:/i.test(norm(text(e))))add(e,text(e),'Attacking label');}
    for(const e of all.filter(e=>['INPUT','SELECT'].includes(e.tagName)||attr(e,'role')==='combobox')){
      const labels=norm([attr(e,'aria-label'),attr(e,'name'),e.id,...[...(e.labels||[])].map(text)].join(' '));
      const v=safeValue(e);if(v&&/model/i.test(labels))add(e,v,'labelled model input value',/search|filter/i.test(labels)||e.type==='search'?'candidate':'confirmed');
      else if(v&&attr(e,'role')==='combobox')add(e,v,'combobox value',e.readOnly?'confirmed':'candidate');
      // Placeholders describe the editor; they are never evidence of selection.
    }
    for(const e of q('[role="listbox"][aria-label="Available models"] [aria-selected="true"],.model-card[aria-selected="true"],select[name*="model"] option:checked').filter(visible))add(e,modelName(e),'selected model option');
    if(args.modelSelector){const es=q(args.modelSelector).filter(visible);if(es.length!==1)throw new Error('Model selector must identify one visible control.');const e=es[0];add(e,safeValue(e)||text(e),'explicit observed model control');}
    const values=[...new Set(candidates.filter(x=>x.confidence==='confirmed').map(x=>x.value))];
    const selected=q('[data-behavior-switch][aria-current="true"],[data-scenario-id][aria-selected="true"]').filter(visible);
    let scenario=selected.length===1?{id:attr(selected[0],'data-behavior-id')||attr(selected[0],'data-scenario-id'),text:text(selected[0]),selector:selector(selected[0])}:null;
    if(!scenario){const numbered=[...new Map(q('h1,h2,h3').filter(visible).filter(e=>/^\d+\.\s+/.test(norm(text(e)))&&!e.closest('[role=dialog],[role=listbox]')).map(e=>[norm(text(e)),e])).values()];if(numbered.length===1)scenario={id:null,key:'title:'+norm(text(numbered[0])),text:text(numbered[0]),selector:selector(numbered[0]),source:'visible numbered scenario heading'};}
    const criteria=q('[data-testid*="criteria" i],[data-testid*="criterion" i],[id*="criteria" i],[aria-label*="success criteria" i],[role="dialog"]').filter(visible).map(e=>({selector:selector(e),text:text(e)})).filter(x=>x.text);
    const messageEls=q('[data-testid="assistantMessage"],[data-testid="userMessage"],[data-message-role],[data-role="assistant"],[data-role="user"],.assistant-message,.model-response,.ai-message').filter(visible);
    const messages=messageEls.filter(e=>!messageEls.some(other=>other!==e&&other.contains(e))).map(e=>({role:attr(e,'data-testid')==='assistantMessage'?'assistant':attr(e,'data-testid')==='userMessage'?'user':attr(e,'data-message-role')||attr(e,'data-role')||'assistant',messageId:attr(e,'data-message-id')||null,text:text(e),selector:selector(e)}));
    // Only explicit judge/result containers or isolated result headings. Never scan chat text for 'success'.
    const judgeEls=q('[data-testid*="judgement" i],[data-testid*="judge-result" i],[data-testid*="submissionResult" i],[data-testid*="breakResult" i],[class*="solved" i],[class*="submissionResult" i],[role="dialog"],h1,h2,h3,h4').filter(visible).filter(e=>!e.closest('[data-testid="assistantMessage"],[data-testid="userMessage"],[data-message-role],[data-role="assistant"],[data-role="user"],.assistant-message,.model-response,.ai-message'));
    const verdicts=judgeEls.map(e=>({selector:selector(e),text:text(e)})).filter(x=>/Break Successful!|SCENARIO SOLVED|Break (Rejected|Unsuccessful|Not Successful)|Submission (Accepted|Rejected|Failed)|Your submission (was not accepted|did not meet)/i.test(x.text));
    const accepted=verdicts.some(x=>/Break Successful!|Submission Accepted|SCENARIO SOLVED/i.test(x.text));
    const rejected=verdicts.some(x=>/Break (Rejected|Unsuccessful|Not Successful)|Submission (Rejected|Failed)|Your submission (was not accepted|did not meet)/i.test(x.text));
    const u=new URL(location.href);const submissionId=u.searchParams.get('submissionId')||q('[data-submission-id]').filter(visible).map(e=>attr(e,'data-submission-id'))[0]||null;
    // Criteria proof rows (per-criterion percentages) as visible on solved screens.
    const criteriaPercents=criteria.map(e=>({selector:e.selector,text:e.text.slice(0,200)})).filter(x=>/\d\s*%/.test(x.text));
    const send=q('#submitChatButton,button[aria-label="Send"],button[aria-label="Send message"] ,[data-testid="sendButton"]').filter(visible);
    const judge=q('#submitJailbreakButton').filter(visible);
    const headings=q('h1,h2,h3,h4,[aria-current="page"]').filter(visible).map(e=>({selector:selector(e),text:text(e)}));
    return {url:location.href,title:document.title,capturedAt:new Date().toISOString(),headings,model:{value:values.length===1?values[0]:null,status:values.length===1?'confirmed':values.length>1?'ambiguous':'unknown',candidates},scenario,criteria,messages,assistantMessages:messages.filter(x=>x.role==='assistant'),judge:{status:accepted&&!rejected?'accepted':rejected&&!accepted?'rejected':'unknown',submissionId,evidence:verdicts,criteriaPercents},streaming:q('[data-state="streaming"],[aria-busy="true"],[data-testid*="typing" i],[data-testid*="generating" i]').some(visible),sendControls:send.map(brief),judgeControls:judge.map(brief),modelPickers:modelPicker().map(brief),availableModels:modelOptions().map(e=>({name:modelName(e),selected:attr(e,'aria-selected')==='true',disabled:!enabled(e),broken:/\bBROKEN\b/.test(text(e)),selector:selector(e)})),links:q('a[href]').filter(visible).map(e=>({text:text(e),href:e.href,selector:selector(e)})),bodyText:document.body?document.body.innerText:''};
  };
  if(args.action==='inspect')return {...getContext(),controls:controls().map(brief),fileInputs:q('input[type="file"]').map(brief)};
  if(args.action==='context')return getContext();
  if(['models','show-criteria','select-model','select-scenario'].includes(args.action)){
    let matches=[];
    if(args.action==='models'){if(modelOptions().length)return {opened:false,alreadyOpen:true};const nested=modelAccordion();matches=nested.length?nested:modelPicker();if(matches.length===1&&attr(matches[0],'aria-expanded')==='true')return {opened:false,alreadyOpen:true};}
    if(args.action==='show-criteria'){matches=q('button,[role="button"]').filter(visible).filter(e=>/^(View scenario criteria|See success criteria|Show success criteria)$/i.test(attr(e,'aria-label')));if(!matches.length)matches=q('button,[role="button"]').filter(visible).filter(e=>/^(See |Show |View )?(success criteria|criteria)$/i.test(norm(text(e))));}
    if(args.action==='select-model')matches=modelOptions().filter(e=>modelName(e)===args.value);
    if(args.action==='select-scenario')matches=q('[data-behavior-switch],[data-scenario-id],[role="button"],button').filter(visible).filter(e=>attr(e,'data-behavior-id')===args.value||attr(e,'data-scenario-id')===args.value||norm(text(e))===args.value);
    matches=[...new Set(matches)];if(matches.length!==1)throw new Error(`Expected one ${args.action} control; found ${matches.length}. Use inspect to check exact controls.`);
    if(!enabled(matches[0]))throw new Error('Selected UI control is disabled.');const mt=matches[0];try{const pev=(ty,C)=>mt.dispatchEvent(new C(ty,{bubbles:true,cancelable:true,pointerType:'mouse',button:0,view:window}));pev('pointerdown',PointerEvent);pev('mousedown',MouseEvent);pev('pointerup',PointerEvent);pev('mouseup',MouseEvent);}catch{}mt.click();return {clicked:true,control:brief(mt)};
  }
  let matches=q(args.selector);
  if(args.action==='read')return {url:location.href,selector:args.selector,matches:matches.map(e=>({...brief(e),text:safeValue(e)??text(e),visible:visible(e)}))};
  if(args.action==='condition'){
    if(args.condition==='hidden')return {met:matches.every(e=>!visible(e)),count:matches.length};
    if(matches.length!==1)return {met:false,count:matches.length};const e=matches[0];
    if(args.condition==='visible')return {met:visible(e),count:1};if(args.condition==='enabled')return {met:enabled(e),count:1};if(args.condition==='text')return {met:text(e)===args.text,count:1};throw new Error('Unknown wait condition.');
  }
  if(matches.length!==1)throw new Error(`Selector must match exactly one element; found ${matches.length}.`);
  const e=matches[0];
  if(args.action==='upload-check'){if(e.tagName!=='INPUT'||e.type!=='file')throw new Error('Upload selector must identify an input[type=file].');if(e.disabled)throw new Error('File input is disabled.');return {multiple:e.multiple,accept:e.accept};}
  if(!enabled(e))throw new Error('Selected control is hidden or disabled.');
  if(args.action==='click'){e.click();return {clicked:true,control:brief(e)};}
  if(args.action==='fill'){
    if(e.tagName==='TEXTAREA'||(e.tagName==='INPUT'&&!['file','password','hidden','submit','button','checkbox','radio'].includes(e.type))){const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(e,args.text);}
    else if(e.isContentEditable)e.textContent=args.text;else throw new Error('Fill supports text inputs, textareas and contenteditable editors.');
    e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return {filled:true,characters:args.text.length,control:brief(e)};
  }
  throw new Error(`Unknown DOM action: ${args.action}`);
}
export const expression=args=>`(${domOperation.toString()})(${JSON.stringify(args)})`;
export const inspect=page=>page.evaluate(expression({action:'inspect'}));
export const context=(page,modelSelector)=>page.evaluate(expression({action:'context',modelSelector}));
export const read=(page,selector)=>page.evaluate(expression({action:'read',selector}));
export const fill=(page,selector,text)=>page.evaluate(expression({action:'fill',selector,text}));
export const click=(page,selector)=>page.evaluate(expression({action:'click',selector}));
export async function upload(page,selector,files){const checked=await page.evaluate(expression({action:'upload-check',selector}));if(files.length>1&&!checked.multiple)throw new Error('This file input does not support multiple files.');const absolute=files.map(f=>{const p=path.resolve(f);if(!fs.statSync(p).isFile())throw new Error('Upload path is not a regular file.');return p;});await page.send('DOM.enable');const doc=await page.send('DOM.getDocument',{depth:0});const nodes=await page.send('DOM.querySelectorAll',{nodeId:doc.root.nodeId,selector});if(nodes.nodeIds.length!==1)throw new Error('File input changed during upload; inspect again.');await page.send('DOM.setFileInputFiles',{nodeId:nodes.nodeIds[0],files:absolute});return {attachedFiles:absolute.map(f=>path.basename(f)),accept:checked.accept};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export async function wait(page,selector,{condition='visible',text='',timeoutMs=30000}={}){const start=Date.now();do{const state=await page.evaluate(expression({action:'condition',selector,condition,text}));if(state.met)return {met:true,condition,elapsedMs:Date.now()-start};await sleep(250);}while(Date.now()-start<timeoutMs);return {met:false,condition,status:'pending',elapsedMs:Date.now()-start};}
export function validateScope(scope,target,origin){
  if(!TRACKS.includes(scope.track)||!scope.scenarioId||!scope.modelId||!scope.observedContext||!['user-scenario','training-link'].includes(scope.evidenceSource))throw new Error('Scope requires track, scenarioId, modelId, observed context and evidenceSource user-scenario or training-link. Proving Ground children are valid when explicitly identified as Training.');
  if(scope.targetId!==target.id||scope.origin!==new URL(origin).origin||scope.url!==target.url)throw new Error('Scope is stale: target, origin or URL changed. Inspect and bind again.');return scope;
}
export function validateObservedContext(scope,snapshot){if(snapshot.url!==scope.url)throw new Error('Tab navigated; bind scope again.');if(snapshot.model.value!==scope.modelId)throw new Error(`Selected model is ${snapshot.model.value||snapshot.model.status}; expected ${scope.modelId}. Inspect input/combobox value or use --model-selector, then bind again.`);if(snapshot.scenario?.id&&snapshot.scenario.id!==scope.scenarioId)throw new Error('Selected scenario changed; bind scope again.');if(scope.scenarioEvidence?.text&&snapshot.scenario?.text!==scope.scenarioEvidence.text)throw new Error('Visible scenario title changed; bind scope again.');}
export async function waitResponse(page,before,{timeoutMs=30000,stableMs=1500}={}){const start=Date.now();let last='',changedAt=start,latest=before;do{latest=await context(page);const fresh=latest.assistantMessages.filter((m,i)=>i>=before.assistantMessages.length||m.text!==before.assistantMessages[i]?.text);const response=fresh.at(-1);if(response?.text!==last){last=response?.text||'';changedAt=Date.now();}if(last&&!latest.streaming&&Date.now()-changedAt>=stableMs)return {status:'observed',response,messages:latest.messages,capturedAt:latest.capturedAt};await sleep(250);}while(Date.now()-start<timeoutMs);return {status:'pending',reason:'No new stable attributed assistant response before timeout; do not resend.',messages:latest.messages,capturedAt:latest.capturedAt};}
export async function waitJudge(page,before,{timeoutMs=30000}={}){const start=Date.now();let latest=before;const key=x=>JSON.stringify(x.judge);do{latest=await context(page);if(['accepted','rejected'].includes(latest.judge.status)&&key(latest)!==key(before))return {...latest.judge,url:latest.url,capturedAt:latest.capturedAt};await sleep(250);}while(Date.now()-start<timeoutMs);return {status:'pending',reason:'No new attributed judge verdict; do not submit again.',observation:latest.judge,url:latest.url,capturedAt:latest.capturedAt};}
function writeJson(file,v){const p=path.resolve(file);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,JSON.stringify(v,null,2)+'\n');}
function appendEvent(file,v){fs.mkdirSync(path.dirname(file),{recursive:true});fs.appendFileSync(file,JSON.stringify(v)+'\n',{mode:0o600});}
export function parseArgs(argv){const r={command:argv[0]||'help'};for(let i=1;i<argv.length;i++){if(!argv[i].startsWith('--'))throw new Error(`Unexpected argument: ${argv[i]}`);const k=argv[i].slice(2);if(i+1>=argv.length||argv[i+1].startsWith('--'))throw new Error(`Value required for --${k}`);if(k in r)throw new Error(`Duplicate option --${k}`);r[k]=argv[++i];}return r;}
const required=(a,k)=>{if(!a[k])throw new Error(`--${k} is required.`);return a[k];};
const HELP=`Gray Swan browser adapter — Node 22+, no npm dependencies
  tabs
  open --url https://app.grayswan.ai/training [--target ID]
  inspect|context --target ID [--out snapshot.json]
  models|show-criteria --target ID
  select-model|select-scenario --target ID --value EXACT_VALUE
  read --target ID --selector CSS [--out snapshot.json]
  bind-scope --target ID --track Chat|Image|Agent|Indirect --scenario-id ID
    --model-id NAME --observed-context TEXT --evidence-source user-scenario|training-link
    [--board "Proving Ground"] [--model-selector CSS] --out scope.json
  fill|upload --scope scope.json --selector CSS --file FILE
  click --scope scope.json --selector CSS --operation-id UNIQUE_ID
  send --scope scope.json --file prompt.txt --operation-id UNIQUE_ID
    [--input-selector CSS] [--selector SEND_BUTTON] [--timeout-ms 30000]
  judge --scope scope.json --operation-id UNIQUE_ID [--selector JUDGE_BUTTON]
  wait --target ID --selector CSS --condition visible|hidden|enabled|text
  screenshot --target ID --out screenshot.png
  dry-run
Common: --cdp http://127.0.0.1:9223 --origin https://app.grayswan.ai
send fills once, clicks once, waits for a NEW full assistant response. It never judges.
judge clicks once and waits for a NEW explicit verdict. Timeout is pending, never victory.
All scope-bound browser mutations are logged. Send/judge/click require an operation ID; reuse is refused.
The user supplies a fresh hypothesis; this package contains no winning prompts.
`;
export async function main(argv=process.argv.slice(2)){
  const a=parseArgs(argv);assertRuntime();if(a.command==='help'){console.log(HELP);return;}if(a.command==='dry-run'){const {runSelfTests}=await import('../tests/engine.test.mjs');await runSelfTests();return;}
  const allowed=['tabs','open','inspect','context','models','show-criteria','select-model','select-scenario','read','bind-scope','fill','click','upload','send','judge','wait','screenshot'];if(!allowed.includes(a.command))throw new Error('Unknown command. Use: node engine/arena.mjs help');
  const known=new Set(['command','cdp','origin','target','selector','out','file','scope','board','track','scenario-id','model-id','observed-context','evidence-source','model-selector','condition','text','timeout-ms','operation-id','event-log','url','value','input-selector']);for(const k of Object.keys(a))if(!known.has(k))throw new Error(`Unknown option --${k}`);
  const cdpUrl=a.cdp||process.env.HACKATHON_CDP_URL||'http://127.0.0.1:9223',origin=new URL(a.origin||'https://app.grayswan.ai').origin;
  if(a.command==='tabs'){console.log(JSON.stringify(matchingTargets(await listTargets(cdpUrl),origin).map(t=>({id:t.id,url:t.url,title:t.title})),null,2));return;}
  if(a.command==='open'){const r=await openTarget({cdpUrl,origin,url:required(a,'url'),targetId:a.target});if(a.out)writeJson(a.out,r);console.log(JSON.stringify(r,null,2));return;}
  const mutation=['fill','click','upload','send','judge'].includes(a.command);const scope=mutation?JSON.parse(fs.readFileSync(required(a,'scope'),'utf8')):null;const targetId=a.target||scope?.targetId;
  const timeoutMs=Number(a['timeout-ms']||30000);if(!Number.isFinite(timeoutMs)||timeoutMs<1||timeoutMs>300000)throw new Error('Timeout must be 1..300000 milliseconds.');
  const {page,target}=await connectPage({cdpUrl,origin,targetId,timeoutMs:Math.min(timeoutMs,15000)});let result,event;
  try{
    let before;
    if(mutation){validateScope(scope,target,origin);before=await context(page,scope.modelSelector);validateObservedContext(scope,before);const eventLog=path.resolve(a['event-log']||path.join(WORKSPACE,'attempts','browser-events.jsonl'));const operationId=['click','send','judge'].includes(a.command)?required(a,'operation-id'):(a['operation-id']||randomUUID());if(fs.existsSync(eventLog)&&fs.readFileSync(eventLog,'utf8').split('\n').filter(Boolean).some(l=>JSON.parse(l).operationId===operationId))throw new Error('Operation ID already used. Reconcile its result before a new operation.');event={eventLog,record:{operationId,at:new Date().toISOString(),action:a.command,track:scope.track,scenarioId:scope.scenarioId,modelId:scope.modelId,targetId,url:target.url,selector:a.selector||null}};appendEvent(eventLog,{...event.record,phase:'started'});}
    if(a.command==='inspect')result=await inspect(page);
    if(a.command==='context')result=await context(page,a['model-selector']);
    if(['models','show-criteria','select-model','select-scenario'].includes(a.command)){if(['models','select-model'].includes(a.command)){for(let step=0;step<2;step++){const opened=await page.evaluate(expression({action:'models'}));if(opened.alreadyOpen)break;await sleep(350);}}const action=a.command==='models'?{opened:true}:await page.evaluate(expression({action:a.command,value:a.value}));await sleep(350);result={...action,snapshot:await inspect(page)};}
    if(a.command==='read')result=await read(page,required(a,'selector'));
    if(a.command==='bind-scope'){const snapshot=await context(page,a['model-selector']);result={board:a.board||'Training',track:required(a,'track'),scenarioId:required(a,'scenario-id'),modelId:required(a,'model-id'),observedContext:required(a,'observed-context'),evidenceSource:required(a,'evidence-source'),modelSelector:a['model-selector']||null,targetId:target.id,origin,url:snapshot.url,capturedAt:snapshot.capturedAt,modelEvidence:snapshot.model,scenarioEvidence:snapshot.scenario};validateScope(result,{...target,url:snapshot.url},origin);validateObservedContext(result,snapshot);writeJson(required(a,'out'),result);}
    if(a.command==='fill')result=await fill(page,required(a,'selector'),fs.readFileSync(required(a,'file'),'utf8'));
    if(a.command==='click')result=await click(page,required(a,'selector'));
    if(a.command==='upload')result=await upload(page,required(a,'selector'),[required(a,'file')]);
    if(a.command==='send'){const prompt=fs.readFileSync(required(a,'file'),'utf8');if(!prompt.trim())throw new Error('Prompt is empty.');const selector=a.selector||(before.sendControls.length===1?before.sendControls[0].selector:null);if(!selector)throw new Error('Send button is ambiguous; inspect and pass --selector.');await fill(page,a['input-selector']||'#chatTextarea',prompt);const ready=await wait(page,selector,{condition:'enabled',timeoutMs:3000});if(!ready.met)throw new Error('Send button stayed disabled after fill; nothing clicked.');await click(page,selector);result={clicked:true,kind:'chat',sentAt:new Date().toISOString(),...await waitResponse(page,before,{timeoutMs})};}
    if(a.command==='judge'){if(before.judge.status!=='unknown')throw new Error('A judge verdict is already visible. Inspect before starting a different submission.');await click(page,a.selector||'#submitJailbreakButton');result={clicked:true,kind:'judge',submittedAt:new Date().toISOString(),...await waitJudge(page,before,{timeoutMs})};}
    if(a.command==='wait')result=await wait(page,required(a,'selector'),{condition:required(a,'condition'),text:a.text||'',timeoutMs});
    if(a.command==='screenshot'){const capture=await page.send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});const dest=path.resolve(required(a,'out'));fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,Buffer.from(capture.data,'base64'));result={saved:dest};}
    if(event){appendEvent(event.eventLog,{...event.record,phase:result.status==='pending'?'pending':'completed',status:result.status||null,submissionId:result.submissionId||null});result.operationId=event.record.operationId;}
    if(a.out&&!['bind-scope','screenshot'].includes(a.command))writeJson(a.out,result);console.log(JSON.stringify(result,null,2));
  }catch(error){if(event)appendEvent(event.eventLog,{...event.record,phase:'unknown',error:String(error.message)});throw error;}finally{page.close();}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main().catch(e=>{console.error(JSON.stringify({error:e.message}));process.exitCode=1;});
