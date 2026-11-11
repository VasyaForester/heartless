#!/usr/bin/env node
// Render a local, escaped document in a fresh isolated Chromium process. No Arena.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {assertRuntime,CdpPage,listTargets} from './engine/cdp.mjs';
const args={};for(let i=2;i<process.argv.length;i+=2){const key=process.argv[i];if(!key.startsWith('--')||!process.argv[i+1])throw new Error('Expected --key value pairs.');args[key.slice(2)]=process.argv[i+1];}
assertRuntime();
const width=Number(args.width),height=Number(args.height);
if(!args.chrome||!args.html||!args.out||!Number.isInteger(width)||!Number.isInteger(height)||width<128||width>2048||height<128||height>2048)throw new Error('Provide chrome, html, out and dimensions 128..2048.');
if(fs.existsSync(args.out))throw new Error('Output already exists.');
const document=fs.readFileSync(args.html,'utf8');
const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'arena-png-browser-'));
const proc=spawn(args.chrome,['--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking','--hide-scrollbars','--force-device-scale-factor=1','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+temporary,'about:blank'],{stdio:['ignore','ignore','pipe']});
let stderr='',startError=null,page=null;proc.stderr.on('data',data=>{stderr=(stderr+data).slice(-4000);});proc.on('error',error=>{startError=error;});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
  const portFile=path.join(temporary,'DevToolsActivePort'),deadline=Date.now()+20000;
  while(!fs.existsSync(portFile)&&Date.now()<deadline&&proc.exitCode===null&&!startError)await sleep(100);
  if(startError)throw startError;
  if(!fs.existsSync(portFile))throw new Error('Chromium did not expose its isolated CDP endpoint. '+stderr.slice(-700));
  const cdpUrl='http://127.0.0.1:'+fs.readFileSync(portFile,'utf8').split('\n')[0];
  const target=(await listTargets(cdpUrl)).find(t=>t.type==='page'&&t.url==='about:blank');
  if(!target)throw new Error('Isolated rendering tab was not created.');
  page=await new CdpPage(target.webSocketDebuggerUrl,10000).connect();
  await page.send('Page.enable');
  await page.send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
  const tree=await page.send('Page.getFrameTree');
  await page.send('Page.setDocumentContent',{frameId:tree.frameTree.frame.id,html:document});
  await page.evaluate('document.fonts.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))).then(() => true)');
  const layout=await page.evaluate('({textClipped:document.querySelector("main").scrollHeight>innerHeight||document.querySelector("main").scrollWidth>innerWidth,contentHeight:document.querySelector("main").scrollHeight})');
  const capture=await page.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false,clip:{x:0,y:0,width,height,scale:1}});
  const bytes=Buffer.from(capture.data,'base64');
  if(bytes.length<24||bytes.subarray(0,8).toString('hex')!=='89504e470d0a1a0a'||bytes.readUInt32BE(16)!==width||bytes.readUInt32BE(20)!==height)throw new Error('Renderer did not return a PNG of the requested dimensions.');
  fs.writeFileSync(args.out,bytes,{flag:'wx'});
  console.log(JSON.stringify({ok:true,width,height,bytes:bytes.length,...layout}));
}catch(error){console.error(JSON.stringify({error:error.message}));process.exitCode=1;}
finally{
  if(page){await page.send('Browser.close').catch(()=>{});page.close();}
  if(proc.exitCode===null){proc.kill('SIGTERM');const end=Date.now()+2000;while(proc.exitCode===null&&Date.now()<end)await sleep(50);if(proc.exitCode===null)proc.kill('SIGKILL');}
  await sleep(150);fs.rmSync(temporary,{recursive:true,force:true,maxRetries:10,retryDelay:100});
}
