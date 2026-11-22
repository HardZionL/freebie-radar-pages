// Smoke tests for the phone redesign without network or a browser runtime.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('site/index.html','utf8');
const script=fs.readFileSync('site/app.js','utf8');
const css=fs.readFileSync('site/style.css','utf8');
const data=JSON.parse(fs.readFileSync('site/data.json','utf8'));
const needed=['menu','drawer-close','drawer-backdrop','mobile-query','mobile-submit','mobile-update','mobile-page-title','query','sidebar','note','results'];
for(const id of needed)assert(html.includes('id="'+id+'"'),'missing '+id);
assert(html.includes('特别感谢原作者'),'credit lost');
assert(css.includes('@media(max-width:760px)'),'responsive missing');
assert(css.includes('.mobile-search-band'),'search not styled');
assert(css.includes('.sidebar.open'),'drawer not styled');
assert(!html.includes('GitHub 配置'),'internal ops exposed');
for(const icon of new Set([...html.matchAll(/data-icon="([a-z]+)"/g)].map(m=>m[1]))){
 assert(fs.existsSync('site/art/nav-'+icon+'.svg'),'missing nav SVG: '+icon);
}
class Element{
 constructor(tag='div'){
  this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.attrs={};this.handlers={};
  this.value='';this.checked=false;this.hidden=false;this.className='';this.textContent='';
  const names=new Set();
  this.classList={add:x=>names.add(x),remove:x=>names.delete(x),contains:x=>names.has(x),
   toggle:x=>names.has(x)?(names.delete(x),false):(names.add(x),true)};
 }
 addEventListener(name,fn){this.handlers[name]=fn}
 setAttribute(name,v){this.attrs[name]=v}
 replaceChildren(...args){this.children=args}
 append(...args){this.children.push(...args)}
 focus(){this.focused=true}
 blur(){this.focused=false}
 scrollIntoView(){this.scrolled=true}
 click(){this.handlers.click?.()}
}
const ids=Object.fromEntries([...html.matchAll(/\bid="([^"]+)"/g)].map(m=>[m[1],new Element()]));
const modes=[...html.matchAll(/<button[^>]+data-mode="([^"]+)"/g)].map(m=>{const e=new Element('button');e.dataset.mode=m[1];return e});
const views=[...html.matchAll(/<button[^>]+data-view="([^"]+)"/g)].map(m=>{const e=new Element('button');e.dataset.view=m[1];return e});
function testSession(phone){
 const node=Object.fromEntries(Object.keys(ids).map(k=>[k,new Element()]));
 const modeBtns=modes.map(x=>{const e=new Element('button');e.dataset.mode=x.dataset.mode;return e});
 const viewBtns=views.map(x=>{const e=new Element('button');e.dataset.view=x.dataset.view;return e});
 node.quality.value='0';node.sort.value='latest';node['show-summary'].checked=true;
 const body=new Element('body');
 const document={body,
  getElementById:k=>node[k],createElement:t=>new Element(t),createTextNode:v=>v,
  querySelectorAll:k=>k==='[data-mode]'?modeBtns:k==='[data-view]'?viewBtns:[],
  addEventListener:()=>{}};
 const stored={};
 const localStorage={getItem:k=>stored[k]??null,setItem:(k,v)=>{stored[k]=v}};
 const window={innerWidth:phone?390:1280,
  matchMedia:q=>({matches:phone?q.includes('max-width'):false}),
  addEventListener:()=>{}};
 const env={document,window,localStorage,fetch:()=>Promise.resolve({ok:true,json:()=>Promise.resolve(data)}),
  URL,Blob,Date,Intl,console,setTimeout};
 const api=vm.runInNewContext(script+
  '\n;({inspect:()=>({mode,view,visible:visible.length}),setMode,showSearchResults})',
  env,{timeout:10000});
 return {node,body,api,modeBtns,viewBtns,stored};
}
(async()=>{
 const {node,body,api,modeBtns,viewBtns,stored}=testSession(true);
 for(let i=0;i<12;i++)await Promise.resolve();
 assert.equal(api.inspect().mode,'daily','default homepage must be daily');
 assert.equal(api.inspect().view,'list','phone must default to readable list');
 assert(node['mobile-update'].textContent.includes('最近更新'),'mobile timestamp missing');
 node.menu.click();
 assert.equal(node.menu.attrs['aria-expanded'],'true');
 assert.equal(node['drawer-backdrop'].hidden,false);
 assert.equal(body.classList.contains('drawer-active'),true);
 node['drawer-close'].click();
 assert.equal(node['drawer-backdrop'].hidden,true);
 assert.equal(body.classList.contains('drawer-active'),false);
 node['mobile-query'].value='红包';node['mobile-query'].handlers.input();
 assert.equal(api.inspect().mode,'search');
 assert.equal(node.query.value,'红包','both search inputs must synchronize');
 assert.equal(node['mobile-page-title'].textContent,'全站搜索');
 assert(api.inspect().visible>=0,'search must render');
 node['mobile-submit'].click();assert(node.note.scrolled,'search button must reach results');
 node['mobile-query'].value='';node['mobile-query'].handlers.input();
 assert.equal(api.inspect().mode,'daily','clearing search should restore previous mode');
 node.query.value='京东';node.query.handlers.input();
 assert.equal(node['mobile-query'].value,'京东','sidebar search sync to mobile');
 node['mobile-query'].value='';node['mobile-query'].handlers.input();
 const voucher=modeBtns.find(x=>x.dataset.mode==='vouchers');assert(voucher);
 voucher.click();assert.equal(api.inspect().mode,'vouchers','voucher shortcut broken');
 viewBtns.find(x=>x.dataset.view==='two').click();
 assert.equal(api.inspect().view,'two');assert.equal(stored['radar.editorial.mobileView'],'"two"');
 const desktop=testSession(false);
 for(let i=0;i<12;i++)await Promise.resolve();
 assert.equal(desktop.api.inspect().mode,'daily');
 assert.equal(desktop.api.inspect().view,'two','desktop preference must stay separate');
 console.log('Mobile search, drawer, navigation, rendering, preferences and privacy: PASS');
})().catch(e=>{console.error(e);process.exitCode=1});
