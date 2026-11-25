"""Free, read-only community discovery: Hacker News Algolia and Product Hunt RSS.

No X API, API key, cookies, proxy bypasses, or arbitrary URL fetching. These
are public promotional *leads*, never official coupon validation.
"""
import datetime as dt
import html as html_lib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode,urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
UTC=dt.timezone.utc
HN_API='https://hn.algolia.com/api/v1/search_by_date'
PH_FEED='https://www.producthunt.com/feed'
KEYWORDS=('free','discount')
PROMO=re.compile(
    r'\bfree\s+(?:trial|credits?|months?|year|plan|tier|pro|premium|subscription|api)\b|'
    r'\b(?:trial|credits?|months?|year)\s+(?:for\s+)?free\b|'
    r'\b(?:discount|coupon|promo code|giveaway|limited.time offer|open.source grant)\b|'
    r'免费试用|免费额度|开发者福利|限时免费|优惠券|限免|红包|折扣|代金券',re.I)
STOP=re.compile(r'账号出售|代充|共享账号|求购|进群|私信|返佣|airdrop|'
                r'crypto presale|giveaway lottery|抽奖|raffle',re.I)
TECH=re.compile(r'\b(?:ai|api|llm|gpt|claude|gemini|developer|coding|open.source|saas|app|tool|software|cloud|model)\b|大模型|开发者|软件',re.I)
FREE=re.compile(r'\b(?:free|freemium|open.source)\b|免费|限免',re.I)
H_ID=re.compile(r'^[0-9]{4,15}$')
P_SLUG=re.compile(r'^/posts/[a-z0-9][a-z0-9-]{1,120}/?$')
MAX_BYTES=900_000
MAX_PER_SOURCE=10

class SameSiteOnly(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        host=urlsplit(newurl).hostname
        if urlsplit(newurl).scheme!='https' or host not in {'hn.algolia.com','www.producthunt.com','producthunt.com'}:
            return None
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def get_public(url,opener=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in {'hn.algolia.com','www.producthunt.com'}:
        raise ValueError('URL not in public allowlist')
    if parsed.hostname=='hn.algolia.com':
        if parsed.path!='/api/v1/search_by_date' or (set(parse_qs(parsed.query)) - {'query','tags','hitsPerPage'}):
            raise ValueError('Unexpected Hacker News search parameters')
    elif url!=PH_FEED:
        raise ValueError('Unexpected Product Hunt URL')
    req=Request(url,headers={'Accept':'application/json,application/atom+xml,application/rss+xml',
        'User-Agent':'ResourceRadar/1.0 (public offers; github.com/HardZionL/freebie-radar-pages)'})
    with (opener or build_opener(SameSiteOnly())).open(req,timeout=14) as res:
        p=urlsplit(res.geturl())
        if p.scheme!='https' or p.hostname not in {'hn.algolia.com','www.producthunt.com','producthunt.com'}:
            raise ValueError('Unexpected redirect target')
        raw=res.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Public feed too large')
        return raw.decode('utf-8',errors='replace')

def parse_date(value):
    try:
        d=dt.datetime.fromisoformat(str(value or '').replace('Z','+00:00'))
        return d.astimezone(UTC) if d.tzinfo else None
    except (ValueError,TypeError,OverflowError):return None

def eligible(title,summary):
    text=title+' '+summary[:250]
    return bool((PROMO.search(text) or (TECH.search(text) and FREE.search(text))) and not STOP.search(text))

def row(source,title,url,summary,published):
    title=' '.join(html_lib.unescape(title).split())[:180]
    summary=' '.join(html_lib.unescape(re.sub(r'<[^>]{0,900}>',' ',summary or '')).split())[:450]
    if not title or len(title)<12 or not eligible(title,summary):return None
    category='ai' if re.search(r'\b(?:AI|API|LLM|Claude|GPT|Gemini|AWS|coding|developer|model|SaaS)\b|大模型|开发',title+' '+summary,re.I) else 'other'
    return {'source_id':source,'title':title,'url':url,'summary':summary or
            '社区公开优惠线索；资格、价格、时效及可用性尚未经过平台核实。',
            'published_at':published.astimezone(UTC).isoformat(timespec='seconds'),
            'expires_at':None,'category':category,'kind':'deal',
            'price':None,'is_free':False,'score':0}

def parse_hn(body,now):
    data=json.loads(body)
    if not isinstance(data,dict) or not isinstance(data.get('hits'),list):raise ValueError('Invalid HN payload')
    out=[]
    for hit in data['hits'][:35]:
        if not isinstance(hit,dict):continue
        ident=str(hit.get('objectID') or '')
        created=parse_date(hit.get('created_at'))
        if not H_ID.fullmatch(ident) or not created or not now-dt.timedelta(days=7)<=created<=now+dt.timedelta(hours=1):
            continue
        title=str(hit.get('title') or '')
        summary=str(hit.get('story_text') or '')
        result=row('hn-offers',title,'https://news.ycombinator.com/item?id='+ident,summary,created)
        if result:out.append(result)
        if len(out)>=MAX_PER_SOURCE:break
    return out

def parse_producthunt(body,now):
    root=ET.fromstring(body)
    out=[]
    # Atom is Product Hunt's official syndication format.
    ns={'atom':'http://www.w3.org/2005/Atom'}
    entries=root.findall('atom:entry',ns)
    if not entries:entries=root.findall('.//item')
    for entry in entries[:50]:
        is_atom=entry.tag.endswith('entry')
        title=entry.findtext('atom:title',default='',namespaces=ns) if is_atom else entry.findtext('title','')
        if is_atom:
            link=next((el.get('href') for el in entry.findall('atom:link',ns)
                       if el.get('href') and el.get('rel','alternate')=='alternate'),None)
            published=entry.findtext('atom:published',default='',namespaces=ns) or entry.findtext('atom:updated',default='',namespaces=ns)
            summary=entry.findtext('atom:content',default='',namespaces=ns) or entry.findtext('atom:summary',default='',namespaces=ns)
        else:
            link=entry.findtext('link','')
            published=entry.findtext('pubDate','')
            summary=entry.findtext('description','')
        p=urlsplit(link or '')
        if p.scheme!='https' or p.hostname not in ('www.producthunt.com','producthunt.com') or not P_SLUG.fullmatch(p.path):continue
        when=parse_date(published)
        if not when:
            try:
                from email.utils import parsedate_to_datetime
                when=parsedate_to_datetime(published).astimezone(UTC)
            except (TypeError,ValueError,OverflowError):continue
        if not now-dt.timedelta(days=5)<=when<=now+dt.timedelta(hours=1):continue
        url='https://www.producthunt.com'+p.path.rstrip('/')
        result=row('producthunt-deals',title or '',url,summary or '',when)
        if result:out.append(result)
        if len(out)>=MAX_PER_SOURCE:break
    return out

def main(path,now=None,opener=None):
    now=now or dt.datetime.now(UTC)
    quick=os.environ.get('RADAR_QUICK')=='true'
    raw=json.loads(path.read_text(encoding='utf-8'))
    existing={str(item.get('url')) for item in raw.get('items',[])}
    new=[]
    selected=(KEYWORDS[(now.hour*2+now.minute//30)%len(KEYWORDS)],) if quick else KEYWORDS
    for query in selected:
        params=urlencode({'query':query,'tags':'story','hitsPerPage':'20'})
        try:
            body=get_public(HN_API+'?'+params,opener)
            scanned=len(json.loads(body).get('hits',[]))
            rows=parse_hn(body,now)
            for r in rows:
                if r['url'] not in existing:existing.add(r['url']);new.append(r)
            print(f'Hacker News free search: scanned {scanned}, {len(rows)} relevant public leads',flush=True)
        except Exception as e:
            print('Hacker News public search unavailable: '+type(e).__name__,flush=True)
    if not quick:
        try:
            body=get_public(PH_FEED,opener)
            scanned=len(ET.fromstring(body))
            rows=parse_producthunt(body,now)
            for r in rows:
                if r['url'] not in existing:existing.add(r['url']);new.append(r)
            print(f'Product Hunt public RSS: {scanned} feed elements, {len(rows)} relevant public leads',flush=True)
        except Exception as e:
            print('Product Hunt public RSS unavailable: '+type(e).__name__,flush=True)
    raw['items'].extend(new[:20])
    path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    print(f'Free community enrichment added {min(20,len(new))}; no external API key or paid X calls',flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: collect_community.py candidates.json')
    main(Path(sys.argv[1]))
