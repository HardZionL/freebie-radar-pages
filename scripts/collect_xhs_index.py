"""Keyless discovery of Xiaohongshu coupon *leads* via public Bing RSS search.

This is NOT the Xiaohongshu API and does not scrape Xiaohongshu pages.
Index coverage is partial; indexed dates do not prove note publication dates.
Only direct canonical public note links and minimal metadata are forwarded to
the existing MiMo screening pipeline. No cookies, images, authors or tokens.
"""
import datetime as dt
import html as html_lib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode,urlsplit,urlunsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
BING='https://www.bing.com/search'
# Fixed queries, never interpolated from untrusted content.
QUERIES=(
  'site:xiaohongshu.com/explore/ 外卖 红包 满减',
  'site:xiaohongshu.com/explore/ 优惠券 无门槛 领取',
  'site:xiaohongshu.com/explore/ 京东 淘宝 会员 免费',
  'site:xiaohongshu.com/explore/ 试用 免费额度 AI',
)
NOTE_RE=re.compile(r'^/(?:explore|discovery/item)/([0-9a-f]{16,32})/?$',re.I)
OFFER_RE=re.compile(
    r'红包|优惠券|无门槛|通用券|抵扣券|代金券|折扣券|满\s*\d+\s*(?:减|-|—)\s*\d+|'
    r'外卖|闪购|立减|免费试用|免费额度|限免|省钱|福利|买一送一|会员折扣',re.I)
RISK_RE=re.compile(
    r'账号出售|租号|代充|拼车|合租|私信|加群|扫码|抽奖|返佣|刷单|兼职|'
    r'薅羊毛群|邀请码交易|破解|盗版',re.I)
MAX_BYTES=650_000
MAX_PER_ROUND=12

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def canonical_note(link):
    try:
        p=urlsplit(link.strip())
        if (p.scheme!='https' or p.hostname not in ('www.xiaohongshu.com','xiaohongshu.com')
             or p.username or p.password or p.port):return None
        m=NOTE_RE.fullmatch(p.path)
        if not m:return None
        return 'https://www.xiaohongshu.com/explore/'+m.group(1).lower()
    except (TypeError,ValueError,AttributeError):
        return None

def clean_title(title):
    value=' '.join(html_lib.unescape(re.sub(r'<[^>]*>',' ',title or '')).split())[:160]
    value=re.sub(r'\s*[-|–]\s*(?:小红书|RedNote|Xiaohongshu)\s*$','',value,flags=re.I).strip()
    return value

def parse_feed(xml_body,seen=None):
    seen=seen if seen is not None else set()
    root=ET.fromstring(xml_body)
    items=root.findall('./channel/item')
    if root.tag!='rss' or root.find('channel') is None:
        raise ValueError('Not a Bing RSS feed')
    out=[]
    for item in items[:25]:
        url=canonical_note(item.findtext('link') or '')
        title=clean_title(item.findtext('title') or '')
        if not url or url in seen or len(title)<10 or not OFFER_RE.search(title) or RISK_RE.search(title):
            continue
        seen.add(url)
        out.append({
            'source_id':'xhs-public-index','title':title,'url':url,
            # No RSS pubDate: search index time is NOT XHS original publication.
            'published_at':None,'expires_at':None,
            'summary':'公开搜索索引发现的小红书笔记标题；未核实优惠金额、领券资格与时效；'
                      '原笔记可能需要小红书 App 打开或已删除。',
            'category':'goods','kind':'deal','price':None,'is_free':False,'score':0,
        })
        if len(out)>=MAX_PER_ROUND:break
    return out

def public_bing_rss(query,opener=None):
    if query not in QUERIES:raise ValueError('Query not allowlisted')
    url=BING+'?'+urlencode({'q':query,'format':'rss'})
    req=Request(url,headers={'User-Agent':'ResourceRadar/1.0 (public search RSS; GitHub Pages)',
      'Accept':'application/rss+xml,application/xml,text/xml'})
    with (opener or build_opener(NoRedirect())).open(req,timeout=12) as res:
        end=urlsplit(res.geturl())
        if end.scheme!='https' or end.hostname!='www.bing.com' or end.path!='/search':
            raise ValueError('Unexpected search redirect')
        content_type=res.headers.get('content-type','').lower()
        if 'html' in content_type and 'xml' not in content_type:
            raise ValueError('Search returned HTML challenge, not RSS')
        raw=res.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Search RSS response too large')
        return raw.decode('utf-8',errors='replace')

def main(path):
    raw=json.loads(path.read_text(encoding='utf-8'))
    seen={canonical_note(x.get('url','')) for x in raw.get('items',[])}
    seen.discard(None)
    collected=[]
    errors=0
    # Two changing keywords per full 2-hour round, limiting search-engine load.
    hour=dt.datetime.now(dt.timezone.utc).hour
    chosen=(QUERIES[hour%len(QUERIES)],QUERIES[(hour+2)%len(QUERIES)])
    for query in chosen:
        try:
            feed=public_bing_rss(query)
            count=len(ET.fromstring(feed).findall('./channel/item'))
            rows=parse_feed(feed,seen)
            collected.extend(rows)
            print(f'XHS public search index: {count} indexed hits, {len(rows)} strict note/coupon leads',flush=True)
        except Exception as e:
            errors+=1
            print('XHS public search index unavailable ('+type(e).__name__+'); no direct XHS access attempted',flush=True)
    raw['items'].extend(collected[:MAX_PER_ROUND])
    path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    print(f'XHS keyless indexed discovery: {len(collected)} candidates; {errors} search-feed failures; '
          'notes may be stale; MiMo review required',flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: collect_xhs_index.py candidates.json')
    main(Path(sys.argv[1]))
