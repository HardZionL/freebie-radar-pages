'use strict';
const $=id=>document.getElementById(id);
const groups={ai:['AI 与开发者','AI & Dev'],shopping:['电商优惠','E-commerce Deals'],media:['影音会员','Media Membership'],other:['其他福利','More Benefits']};
const sources={'linuxdo-welfare':'LINUX DO','v2ex-free':'V2EX 免费赠送','v2ex-deals':'V2EX 优惠','rss-smzdm':'什么值得买','rss-smzdm-coupon':'值得买·领券频道','rss-smzdm-delivery':'值得买·外卖频道','aws-official-ai':'AWS 官方 AI 公告','aws-quick-official':'AWS Quick 官方文档','hn-offers':'Hacker News 社区优惠','producthunt-deals':'Product Hunt 新品优惠','rss-fuliba':'福利吧','rss-ithome':'IT之家','openrouter-free':'OpenRouter','rss-nodeseek':'NodeSeek','epic-free':'Epic','gamerpower':'GamerPower'};
const modes={all:'资源流',hot:'今日热点',daily:'每日精选',retail:'购物线索 · 待核实',vouchers:'红包与优惠券',search:'全站搜索',deadline:'今日截止',favorites:'我的收藏',hidden:'已关闭'};
function loadLocal(key,fallback){try{return JSON.parse(localStorage.getItem('radar.editorial.'+key))??fallback}catch{return fallback}}
function store(key,value){try{localStorage.setItem('radar.editorial.'+key,JSON.stringify(value))}catch{}}
const setLocal=key=>{const v=loadLocal(key,[]);return new Set(Array.isArray(v)?v:[])};
const fav=setLocal('favorites'),read=setLocal('read'),closed=setLocal('closed');
let data={items:[],daily:[],shoppingLeads:[],officialBenefits:[]},mode='daily',returnMode='daily',bucket='',view=loadLocal('view','two'),visible=[];
if(!['list','two','three'].includes(view))view='two';
if(window.matchMedia('(max-width: 760px)').matches){
 const mobileChoice=loadLocal('mobileView','list');
 view=['list','two','three'].includes(mobileChoice)?mobileChoice:'list';
}
function el(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=String(text);if(cls)e.className=cls;return e}
function button(text,action,pressed){const b=el('button',text);b.type='button';if(pressed!==undefined)b.setAttribute('aria-pressed',String(pressed));b.addEventListener('click',action);return b}
function dateKey(v){const d=new Date(v);if(!v||Number.isNaN(d.getTime()))return '';return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(d)}
function time(v){if(!v)return '未知';const d=new Date(v);return Number.isNaN(d.getTime())?'未知':new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(d)}
function stamp(x){const n=Date.parse(x.published||x.firstSeen);return Number.isFinite(n)?n:0}
const couponNames={coupon:'抵扣／优惠券',redpacket:'平台红包',delivery:'外卖／闪购券'};
function offerType(x){
 if(['coupon','redpacket','delivery'].includes(x.offerType))return x.offerType;
 const t=x.title||'';
 if(!/红包|优惠券|代金券|券包|领券|神券|无门槛|满\s*\d+\s*(?:减|-|—)\s*\d+|每日可领|支付立减/.test(t))return 'product';
 if(/外卖|闪购|饿了么/.test(t))return 'delivery';
 if(/红包|赠金/.test(t))return 'redpacket';
 return 'coupon'
}
function union(){return Array.from(new Map([...(data.shoppingLeads||[]),...data.daily.flatMap(d=>d.items||[]),...data.items,...(data.officialBenefits||[])].map(x=>[x.id,x])).values())}
function todayDue(x){return dateKey(x.expires)===dateKey(Date.now())&&Date.parse(x.expires)>Date.now()}
function getBase(){if(mode==='search')return union();if(mode==='vouchers')return union().filter(x=>offerType(x)!=='product');if(mode==='retail')return data.shoppingLeads||[];if(mode==='daily')return data.daily.find(d=>d.date===$('date').value)?.items||[];if(mode==='favorites')return union().filter(x=>fav.has(x.id));if(mode==='hidden')return union().filter(x=>closed.has(x.id));if(mode==='hot')return data.items.filter(x=>stamp(x)>Date.now()-86400000&&x.quality>=4);if(mode==='deadline')return data.items.filter(todayDue);return [...(data.officialBenefits||[]),...data.items]}
function closeMenu(restoreFocus=false){
 $('sidebar').classList.remove('open');
 $('drawer-backdrop').hidden=true;
 $('menu').setAttribute('aria-expanded','false');
 document.body.classList.remove('drawer-active');
 if(restoreFocus && window.matchMedia('(max-width: 760px)').matches) $('menu').focus();
}
function openMenu(){
 $('sidebar').classList.add('open');
 $('drawer-backdrop').hidden=false;
 $('menu').setAttribute('aria-expanded','true');
 document.body.classList.add('drawer-active');
 $('drawer-close').focus();
}
function setMode(next){
 if(!(next in modes))return;
 mode=next;returnMode=next;bucket='';
 $('query').value='';$('mobile-query').value='';
 $('source').value='';$('period').value='';$('unread').checked=false;
 $('sort').value=mode==='hot'?'quality':mode==='deadline'?'expiry':mode==='vouchers'||mode==='retail'?'coupon':'latest';
 closeMenu();render();
}
function toggle(set,k,id){if(set.has(id))set.delete(id);else set.add(id);store(k,[...set]);render()}
function card(x){
 const kind=offerType(x),unverified=x.reviewStatus==='unverified';const a=el('article',null,'item'+(read.has(x.id)?' read':'')+(kind!=='product'?' voucher-card':'')+(unverified?' unverified':'')), art=el('div',null,'thumb');a.dataset.offer=kind;art.dataset.art=groups[x.bucket]?x.bucket:'other';art.setAttribute('aria-hidden','true');a.append(art);
 const body=el('div',null,'item-content'),head=el('div',null,'item-top');const score=el('span',x.reviewStatus==='official-confirmed'?'官方条款已核验':x.reviewStatus==='unverified'?'尚未核实':'★ '+x.quality+'/5','quality');score.dataset.score=x.quality;head.append(el('span',kind!=='product'?(couponNames[kind]||'优惠信息'):(groups[x.bucket]||groups.other)[0],'tag'),score);const headline=el('h3',x.title);headline.title=x.title;body.append(head,headline);
 if($('show-summary').checked)body.append(el('p',x.reason||'活动信息以原平台为准','reason'));
 const meta=el('div',null,'meta');meta.append(el('span',sources[x.source]||x.source),el('span',x.reviewStatus==='official-confirmed'?'官方核验 '+(x.verifiedAt||'以原文为准'):(x.published?'发布':'发现')+' '+time(x.published||x.firstSeen)),el('span',x.reviewStatus==='official-confirmed'?'活动条件以 AWS 官方为准':x.expires?'截止 '+time(x.expires):'截止未注明'));if(typeof x.price==='number')meta.append(el('span','来源提取价 '+x.price+'（币种待核）'));body.append(meta);
 const links=el('div',null,'links');
 try{const url=new URL(x.url);if(url.protocol==='https:'&&!url.username&&!url.password){const a=el('a',x.reviewStatus==='official-confirmed'?'查看 AWS 官方条款 ↗':unverified?'查看原文核实 ↗':kind!=='product'?'查看活动详情 ↗':'查看原始信息 ↗','visit-link');a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';a.addEventListener('click',()=>{read.add(x.id);store('read',[...read]);render()});links.append(a)}}catch{}
 const star=button('',()=>toggle(fav,'favorites',x.id),fav.has(x.id));star.className='action-button action-fav';star.title=fav.has(x.id)?'取消收藏':'收藏';star.setAttribute('aria-label',star.title);
 const seen=button('',()=>toggle(read,'read',x.id),read.has(x.id));seen.className='action-button action-read';seen.title=read.has(x.id)?'标记未读':'标记已读';seen.setAttribute('aria-label',seen.title);
 const hide=button('',()=>toggle(closed,'closed',x.id),closed.has(x.id));hide.className='action-button action-hide';hide.title=closed.has(x.id)?'恢复资源':'关闭资源';hide.setAttribute('aria-label',hide.title);links.append(star,seen,hide);body.append(links);a.append(body);return a
}
function sourceMenu(){const list=$('source-list');list.replaceChildren();const selected=$('source').value;for(const [id,name] of [['','全部来源'],...Object.entries(sources)]){const countPool=mode==='retail'?(data.shoppingLeads||[]):mode==='search'||mode==='vouchers'||mode==='favorites'?union():[...(data.officialBenefits||[]),...data.items];const n=countPool.filter(x=>!id||x.source===id).length;const b=button(name,()=>{$('source').value=id;render()},id===selected);b.append(el('b',n));list.append(b)}}
function renderInsights(){
 const aside=$('insights'),list=$('insight-list');
 aside.hidden=mode!=='daily';
 if(mode!=='daily'){list.replaceChildren();return}
 list.replaceChildren();
 const items=(data.daily.find(d=>d.date===$('date').value)?.items||[]).filter(x=>!closed.has(x.id));
 for(const [key,[name]] of Object.entries(groups)){
   const rows=items.filter(x=>x.bucket===key);
   const tile=button('',()=>{bucket=key;render()},bucket===key);
   tile.className='insight-tile';
   tile.dataset.bucket=key;
   const header=el('div',null,'insight-tile-head');
   const glyph=el('span',null,'insight-icon');glyph.dataset.bucket=key;
   header.append(glyph,el('strong',name),el('b',rows.length));
   tile.append(header,el('p',rows.length?rows.slice().sort((a,b)=>b.quality-a.quality)[0].title:'本期暂无该类精选'));
   list.append(tile);
 }
}
function renderOfficial(){
 const root=$('official-spotlight');
 const item=(data.officialBenefits||[]).find(x=>x.source==='aws-quick-official'&&x.reviewStatus==='official-confirmed');
 root.hidden=mode!=='daily'||!item;
 if(!item)return;
 $('official-title').textContent=item.title;
 $('official-detail').textContent=item.reason;
 $('official-verified').textContent='来源：AWS 官方文档 · 官方核验日期：'+(item.verifiedAt||'以原文为准')+' · 非 Claude API 额度';
 $('official-link').href=item.url;
}
function render(){
 $('crumb').textContent=modes[mode];$('mobile-page-title').textContent=modes[mode];document.body.classList.toggle('search-active',mode==='search');$('heading').replaceChildren(document.createTextNode(mode==='all'?'资源雷达':modes[mode]),el('span','.'));$('subtitle').textContent=mode==='daily'?'每日甄选公开福利 · 把值得关注的好东西一次看完':mode==='hot'?'近 24 小时 AI 评分较高的资源 · 非社区热度排名':mode==='retail'?'公开商品优惠线索，尚未经过 AI 审核':mode==='vouchers'?'集中展示平台抵扣券、无门槛红包和外卖优惠，审核状态分别标注':mode==='search'?'全站搜索：已审核资源 + 未审核购物线索':'寻找真正有价值的资源，让信息有序浮现。';
 document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
 $('nav-count').textContent=data.items.length;$('overview').hidden=mode!=='daily';$('retail-banner').hidden=mode!=='daily';$('retail-count').textContent=(data.shoppingLeads||[]).length;$('coupon-count').textContent=union().filter(x=>offerType(x)!=='product').length;$('controls').hidden=false;$('export').disabled=false;$('content-shell').classList.toggle('daily-layout',mode==='daily');sourceMenu();renderInsights();renderOfficial();
 const target=$('results');target.replaceChildren();target.className='';
 let base=getBase();if(mode!=='hidden')base=base.filter(x=>!closed.has(x.id));
 if(mode==='daily'){$('total').textContent=base.length;$('deals').textContent=base.filter(x=>x.reason?.includes('优惠')||x.reason?.includes('会员')).length;$('due').textContent=base.filter(todayDue).length;$('high').textContent=base.filter(x=>x.quality===5).length;$('summary').textContent=base.length?'本期共 '+base.length+' 条精选，涵盖 '+Object.keys(groups).filter(k=>base.some(x=>x.bucket===k)).map(k=>groups[k][0]).join('、')+'。不凑数，活动细节以原平台为准。':'暂无符合精选标准的资源，晚间云端更新后可查看。'}
 const channel=$('channels');channel.replaceChildren();for(const [key,label] of [['','全部分类'],...Object.entries(groups).map(([k,v])=>[k,v[0]])]){const n=base.filter(x=>!key||x.bucket===key).length;const pill=button('',()=>{bucket=key;render()},bucket===key);pill.className='channel-pill';pill.append(el('span',label,'channel-name'),el('span',n,'channel-count'));channel.append(pill)}
 const query=$('query').value.trim().toLowerCase(),src=$('source').value,period=Number($('period').value),minQuality=Number($('quality').value),price=$('price').value,expiry=$('expiry').value;
 let rows=base.filter(x=>(!bucket||x.bucket===bucket)&&(!src||x.source===src)&&(!query||[x.title,x.reason,sources[x.source],(groups[x.bucket]||groups.other)[0]].join(' ').toLowerCase().includes(query))&&(!period||stamp(x)>=Date.now()-period*3600000)&&(mode==='retail'||x.quality>=minQuality)&&(!$('unread').checked||!read.has(x.id))&&(!price||(price==='free'&&x.price===0)||(price==='paid'&&typeof x.price==='number'&&x.price>0)||(price==='unknown'&&x.price==null))&&(!expiry||(expiry==='known'&&x.expires)||(expiry==='unknown'&&!x.expires)));
 const sort=$('sort').value;rows.sort((a,b)=>sort==='coupon'?((offerType(a)==='product')-(offerType(b)==='product')||((a.reviewStatus==='unverified')-(b.reviewStatus==='unverified'))||stamp(b)-stamp(a)):sort==='quality'?b.quality-a.quality||stamp(b)-stamp(a):sort==='expiry'?(Date.parse(a.expires)||Infinity)-(Date.parse(b.expires)||Infinity)||stamp(b)-stamp(a):stamp(b)-stamp(a));visible=rows;$('count').textContent='共 '+rows.length+' 条';$('note').textContent=(mode==='daily'?$('date').value||'等待晚间日报':mode==='all'?'近 7 天已审核资源':modes[mode])+' · '+rows.length+(mode==='retail'?' 条 · 公开购物线索，未经 AI 审核':mode==='vouchers'||mode==='search'?' 条 · 同时包含 AI 初筛资源和待核实线索，请按标签区分':' 条 · 插画为类别装饰，非商品实拍');
 if(!rows.length){target.append(el('div','◇  暂无符合当前条件的资源。可以调整筛选；云端每两小时更新。','empty'));return}
 if(mode==='daily'&&!bucket&&view==='two')target.className='group-grid';
 for(const [key,[name,en]] of Object.entries(groups)){const list=rows.filter(x=>x.bucket===key);if(!list.length)continue;const group=el('section',null,'group'),head=el('div',null,'group-head');const pixel=el('span',null,'pix');pixel.dataset.bucket=key;head.append(pixel,el('h2',name),el('em',en));if(!bucket)head.append(button('查看本类 →',()=>{bucket=key;render()}));group.append(head);const cards=el('div',null,'cards '+view);for(const x of list)cards.append(card(x));group.append(cards);target.append(group)}
}
for(const b of document.querySelectorAll('[data-mode]'))b.addEventListener('click',()=>setMode(b.dataset.mode));
for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>{view=b.dataset.view;store(window.matchMedia('(max-width: 760px)').matches?'mobileView':'view',view);render()});
function searchChanged(next,origin){
 // Both search fields share one source of truth; typing anywhere always searches
 // across reviewed items and distinctly unverified shopping leads.
 if(origin!=='query')$('query').value=next;
 if(origin!=='mobile-query')$('mobile-query').value=next;
 const q=next.trim();
 if(q && mode!=='search'){
   returnMode=mode;mode='search';bucket='';$('source').value='';$('period').value='';$('sort').value='coupon';
 }
 if(!q && mode==='search'){mode=returnMode;$('sort').value=mode==='vouchers'||mode==='retail'?'coupon':'latest'}
 render();
}
$('query').addEventListener('input',()=>searchChanged($('query').value,'query'));
$('mobile-query').addEventListener('input',()=>searchChanged($('mobile-query').value,'mobile-query'));
function showSearchResults(){
 if($('mobile-query').value.trim() && mode!=='search')searchChanged($('mobile-query').value,'mobile-query');
 $('mobile-query').blur();
 $('note').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
}
$('mobile-submit').addEventListener('click',showSearchResults);
$('mobile-query').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();showSearchResults()}});

for(const k of ['date','source','period','sort','unread','show-summary','quality','price','expiry'])$(k).addEventListener('input',render);
$('advanced').addEventListener('click',()=>{const open=$('advanced-panel').hidden;$('advanced-panel').hidden=!open;$('advanced').setAttribute('aria-expanded',String(open))});
$('reset').addEventListener('click',()=>{for(const id of ['query','mobile-query','source','period','price','expiry'])$(id).value='';$('quality').value='0';$('unread').checked=false;bucket='';if(mode==='search'){mode=returnMode;$('sort').value='latest'}render()});
$('menu').addEventListener('click',()=>$('sidebar').classList.contains('open')?closeMenu(true):openMenu());
$('drawer-close').addEventListener('click',()=>closeMenu(true));
$('drawer-backdrop').addEventListener('click',()=>closeMenu(true));
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'&&$('sidebar').classList.contains('open')){closeMenu(true);return}
 if(e.key==='/'&&!['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)){
   e.preventDefault();
   if(window.matchMedia('(max-width: 760px)').matches){closeMenu();$('mobile-query').focus()}
   else $('query').focus();
 }
});
window.addEventListener('resize',()=>{if(window.innerWidth>760 && $('sidebar').classList.contains('open'))closeMenu()});
$('export').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(visible,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='radar-resources.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
for(const [id,name] of Object.entries(sources)){const op=el('option',name);op.value=id;$('source').append(op)}
fetch('./data.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('data');return r.json()}).then(s=>{if(!Array.isArray(s.items)||!Array.isArray(s.daily)||!Array.isArray(s.shoppingLeads))throw Error('schema');data=s;$('update').textContent=s.updatedAt?'最近更新（北京） '+time(s.updatedAt):'等待首次云端更新';$('mobile-update').textContent=s.updatedAt?'最近更新（北京） '+time(s.updatedAt):'等待首次云端更新';data.daily.sort((a,b)=>b.date.localeCompare(a.date));for(const d of data.daily){const op=el('option',d.date);op.value=d.date;$('date').append(op)}if(data.daily.length)$('date').value=data.daily[0].date;render()}).catch(()=>{$('note').textContent='数据加载失败，请稍后刷新。'});
