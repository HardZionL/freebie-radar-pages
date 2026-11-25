// Copied into pinned upstream checkout; no AI credentials in this process.
import { migrate, get, all, run } from './src/server/db.ts';
import { ensureSources, runSource } from './src/server/collectors/index.ts';
import { writeFileSync } from 'node:fs';
const output = process.argv[2];
if (!output) throw new Error('output path required');
migrate(); ensureSources();
const bootstrap = process.env.RADAR_BOOTSTRAP === 'true';
const retail = process.env.RADAR_RETAIL === 'true';
const quick = process.env.RADAR_QUICK === 'true';
const maxPerSource = bootstrap ? 40 : retail ? 35 : quick ? 10 : 20;
const regular = [
  'linuxdo-welfare','v2ex-free','v2ex-deals','rss-smzdm','rss-fuliba',
  'rss-ithome','openrouter-free','rss-nodeseek','epic-free','gamerpower',
  'rss-meta-appinn','rss-sharewareonsale','rss-giveawayoftheday',
  'rss-isthereanydeal','rss-9to5toys',
];
const fast = ['linuxdo-welfare','v2ex-free','v2ex-deals','rss-smzdm',
  'openrouter-free','rss-nodeseek','rss-meta-appinn'];
const initialOnly = ['rss-itch-free','gamerpower-loot'];
const ids = bootstrap ? [...regular, ...initialOnly]
  : retail ? ['rss-smzdm','v2ex-deals','rss-fuliba','rss-meta-appinn','rss-9to5toys']
  : quick ? fast : regular;
console.log(bootstrap ? 'INITIAL BACKFILL: increased source scan' : retail ? 'RETAIL CHECK: shopping-first one-off validation' : 'NORMAL UPDATE: '+(quick?'30-minute fast incremental collection':'2-hour full source rotation'));
const words = ['淘宝','天猫','京东','拼多多','88VIP','PLUS会员','腾讯视频','爱奇艺','优酷','芒果','哔哩哔哩','B站大会员','大会员','联合会员','年卡','折扣','特价','好价','史低','直降','立减','降价','购物津贴','券后','低价','网易云音乐','QQ音乐','会员','红包','免单','优惠券','限免','学生优惠','话费','外卖','美团','饿了么','满减','大促','史低','百亿补贴','五折','半价','免费领取'];
for (const id of ['rss-smzdm','rss-fuliba','rss-ithome','rss-nodeseek']) {
  const row=get('SELECT config FROM sources WHERE id = ?',id);
  if (!row) continue;
  const cfg=JSON.parse(row.config);
  for (const f of cfg.feeds ?? []) {
    f.limit=maxPerSource;
    // The original www.smzdm.com/rss/ endpoint serves lifestyle articles
    // linking to post.smzdm.com. The public SMZDM deal RSS is feed.smzdm.com.
    // It is read-only and all item links pass strict host+scheme sanitization.
    if(id==='rss-smzdm') f.url='http://feed.smzdm.com/';
    // Do not require "淘宝/京东" in a merchant product headline.
    f.titleKeywords=id==='rss-smzdm' ? [] : id==='rss-nodeseek'
      ? ['免费','白嫖','限免','福利','赠','free','0元','特价','黑五','优惠','促销','赠送']
      : words;
    f.excludeTitleKeywords=['账号出售','代充','求购','共享账号','拼车','合租','返佣'];
    if(id==='rss-nodeseek') f.includeCategories=['info','promotion'];
  }
  run('UPDATE sources SET config=? WHERE id=?',JSON.stringify(cfg),id);
}
const results=[];
for(const id of ids){
  try {
    const r=await runSource(id,{maxItems:maxPerSource,log:()=>{}});
    results.push({id,status:r.status,fetched:r.fetched,inserted:r.inserted});
    console.log(id+': '+r.status+', '+r.fetched+' fetched');
  } catch { results.push({id,status:'failed',fetched:0,inserted:0}); console.log(id+': failed'); }
}
const items=all("SELECT source_id,title,url,summary,published_at,expires_at,category,kind,price,is_free,score FROM items WHERE status='active'");
writeFileSync(output,JSON.stringify({items,sources:results,bootstrap,retail}));
if(!results.some(r=>r.status==='ok'||r.status==='degraded')) process.exitCode=1;
