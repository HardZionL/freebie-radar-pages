"""Read-only first-party AI benefit monitor. No accounts, cookies or API keys."""
import datetime as dt
import html as html_lib
import json
import re
import sys
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
DOCS='https://docs.aws.amazon.com/quick/latest/userguide/standalone-plans.html'
FEEDS=(
    'https://aws.amazon.com/blogs/machine-learning/feed/',
    'https://aws.amazon.com/blogs/aws/category/artificial-intelligence/feed/',
    'https://aws.amazon.com/blogs/aws/feed/',
)
PROMO=re.compile(r'free (?:trial|tier|credits?|plan)|\btrial\b|no.cost|no charge|'
                 r'promotion|discount|student|free and plus|credits? for|'
                 r'免费|试用|抵扣|额度|优惠|赠送',re.I)
MAX_BYTES=4_000_000
UTC=dt.timezone.utc

class NoOffsite(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        p=urlsplit(newurl)
        allowed={'aws.amazon.com','docs.aws.amazon.com'}
        if p.scheme!='https' or p.hostname not in allowed:
            return None
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.words=[]
        self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('script','style') and self.hidden:self.hidden-=1
    def handle_data(self,v):
        if not self.hidden:self.words.append(v)

def read_public(url,kind,opener=None):
    if url not in FEEDS+(DOCS,):raise ValueError('Source not allowlisted')
    opener=opener or build_opener(NoOffsite())
    req=Request(url,headers={'User-Agent':'ResourceRadar/1.0 (+https://github.com/HardZionL/freebie-radar-pages)',
                             'Accept':'text/html,application/rss+xml,application/xml'})
    with opener.open(req,timeout=12) as res:
        final=urlsplit(res.geturl())
        if final.scheme!='https' or final.hostname not in {'aws.amazon.com','docs.aws.amazon.com'}:
            raise ValueError('Redirect not allowed')
        body=res.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:raise ValueError('Oversize official page')
        return body.decode('utf-8',errors='replace')

def quick_trial_is_confirmed(content):
    parser=TextOnly()
    parser.feed(content)
    text=' '.join(' '.join(parser.words).split())
    return bool(re.search(r'new accounts receive 30 days of plus at no cost|'
                          r'(?:every new signup|every customer who signs up).{0,130}'
                          r'(?:free )?30.day trial of (?:the )?plus',text,re.I))

def safe_blog_link(link):
    try:
        p=urlsplit(link.strip())
        if p.scheme!='https' or p.hostname!='aws.amazon.com' or p.username or p.password:return None
        if not p.path.startswith('/blogs/') or len(p.path)>350:return None
        return urlunsplit(('https','aws.amazon.com',p.path,'',''))
    except (ValueError,AttributeError):return None

def parse_rss(content,now):
    root=ElementTree.fromstring(content)
    out=[]
    for node in root.findall('.//item')[:35]:
        title=' '.join((node.findtext('title') or '').split())[:180]
        link=safe_blog_link(node.findtext('link') or '')
        desc=html_lib.unescape(node.findtext('description') or '')
        summary=' '.join(re.sub(r'<[^>]{0,1500}>',' ',desc).split())[:450]
        pub=node.findtext('pubDate') or ''
        try:
            when=parsedate_to_datetime(pub).astimezone(UTC)
        except (ValueError,TypeError,IndexError,OverflowError):continue
        if when<now-dt.timedelta(days=10) or when>now+dt.timedelta(days=1):continue
        if not title or not link or not PROMO.search(title+' '+summary[:180]):continue
        out.append({'source_id':'aws-official-ai','title':title,'url':link,
            'summary':summary or 'AWS 官方文章；是否有领取活动、资格及限制请以原文为准',
            'published_at':when.isoformat(timespec='seconds'),'expires_at':None,
            'category':'ai','kind':'announcement','price':None,'is_free':False,'score':0})
        if len(out)>=12:break
    return out

def main(path,root=ROOT,opener=None,now=None):
    now=now or dt.datetime.now(UTC)
    raw=json.loads(path.read_text(encoding='utf-8'))
    known={x.get('url') for x in raw.get('items',[])}
    found=[]
    for feed in FEEDS:
        try:
            results=parse_rss(read_public(feed,'rss',opener),now)
            for row in results:
                if row['url'] not in known:
                    known.add(row['url']);found.append(row)
        except Exception as e:
            print('AWS official RSS unavailable ('+feed+'): '+type(e).__name__+': '+str(e)[:140],flush=True)
    raw['items'].extend(found[:20])
    seed=json.loads((root/'scripts/official-benefits.json').read_text(encoding='utf-8'))
    offer=seed[0]
    if offer.get('url')!=DOCS or offer.get('source')!='aws-quick-official':
        raise ValueError('Invalid editorial source')
    verified=False
    try:
        verified=quick_trial_is_confirmed(read_public(DOCS,'html',opener))
    except Exception as e:
        print('AWS Quick documentation not reachable: '+type(e).__name__,flush=True)
    if verified:
        offer['verifiedAt']=now.isoformat(timespec='seconds')
        print('AWS Quick 30-day Plus trial verified against first-party docs',flush=True)
    else:
        # A stale seeded claim may not be advertised as newly verified forever.
        recorded=dt.datetime.fromisoformat(offer['verifiedAt'].replace('Z','+00:00'))
        if recorded.tzinfo is None:recorded=recorded.replace(tzinfo=UTC)
        if (now-recorded)>dt.timedelta(days=14):
            offer=None
    raw['officialBenefits']=[offer] if offer else []
    path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    print(f'AWS first-party AI offer monitoring: {len(found)} new RSS candidates; '
          f'{len(raw["officialBenefits"])} verified policy notes; AI model in Quick not asserted',flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: collect_official_ai.py candidates.json')
    main(Path(sys.argv[1]))
