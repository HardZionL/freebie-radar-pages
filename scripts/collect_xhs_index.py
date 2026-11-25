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
GITHUB_ISSUES='https://api.github.com/repos/HardZionL/freebie-radar-pages/issues?state=open&per_page=30'
ISSUE_TITLE_PREFIX='[小红书优惠]'
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

def parse_public_issues(blob,now,seen):
    """Accept public volunteer submissions, never arbitrary linked web content.

    Uses GitHub's own issue creation timestamp, not submitted/pasted dates.
    No user identity or issue body is persisted to the public snapshot.
    """
    if not isinstance(blob,list) or len(blob)>30:
        raise ValueError('Unexpected public GitHub issue listing')
    out=[]
    note_pattern=re.compile(
        r'https://(?:www\.)?xiaohongshu\.com/(?:explore|discovery/item)/[0-9a-f]{16,32}(?:\?[^\s)>\]]*)?',
        re.I)
    for issue in blob:
        if not isinstance(issue,dict) or issue.get('state')!='open' or issue.get('pull_request'):
            continue
        headline=str(issue.get('title') or '').strip()
        if not headline.startswith(ISSUE_TITLE_PREFIX):
            continue
        title=clean_title(headline[len(ISSUE_TITLE_PREFIX):].strip())
        body=str(issue.get('body') or '')[:4000]
        match=note_pattern.search(body)
        url=canonical_note(match.group(0).rstrip('.,;') if match else '')
        try:
            submitted=dt.datetime.fromisoformat(str(issue.get('created_at') or '').replace('Z','+00:00'))
            if submitted.tzinfo is None:continue
            age=(now-submitted.astimezone(dt.timezone.utc)).total_seconds()
        except (ValueError,TypeError):
            continue
        if url is None or url in seen or len(title)<10 or not OFFER_RE.search(title) or RISK_RE.search(title):
            continue
        if age<0 or age>7*86400:
            continue
        seen.add(url)
        out.append({
            'source_id':'xhs-community','title':title,'url':url,
            'published_at':None,'expires_at':None,
            'summary':'GitHub 读者提交的小红书公开优惠笔记线索；未核实内容、金额、资格或时效。'
                      '仅提供原始笔记链接，可能需要在小红书 App 中按标题搜索。',
            'category':'goods','kind':'deal','price':None,'is_free':False,'score':0,
        })
        if len(out)>=MAX_PER_ROUND:
            break
    return out

def public_github_issues(opener=None):
    req=Request(GITHUB_ISSUES,headers={
        'Accept':'application/vnd.github+json',
        'User-Agent':'ResourceRadar/1.0 (public GitHub issue submissions)'})
    with (opener or build_opener(NoRedirect())).open(req,timeout=12) as res:
        end=urlsplit(res.geturl())
        if (end.scheme!='https' or end.hostname!='api.github.com' or
                end.path!='/repos/HardZionL/freebie-radar-pages/issues'):
            raise ValueError('Unexpected GitHub API redirect')
        raw=res.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError('Public issue response too large')
        return json.loads(raw)

def parse_curated(blob,now,seen):
    if not isinstance(blob,list) or len(blob)>30:
        raise ValueError('Curated input must be an array with at most 30 entries')
    rows=[]
    for item in blob:
        if not isinstance(item,dict):continue
        url=canonical_note(str(item.get('url') or ''))
        title=clean_title(str(item.get('title') or ''))
        when=str(item.get('addedOn') or '')
        try:
            entered=dt.date.fromisoformat(when)
        except ValueError:
            continue
        if (url is None or url in seen or len(title)<10 or
            not OFFER_RE.search(title) or RISK_RE.search(title) or
            entered>now.date() or (now.date()-entered).days>7):
            continue
        seen.add(url)
        rows.append({
            'source_id':'xhs-curated','title':title,'url':url,
            'published_at':None,'expires_at':None,
            'summary':'站长提供的公开小红书优惠笔记线索；只核对了标题和原始网址，'
                      '尚未实测活动与领取条件；原帖可能要求在小红书 App 内搜索标题。',
            'category':'goods','kind':'deal','price':None,'is_free':False,'score':0,
        })
        if len(rows)>=MAX_PER_ROUND:break
    return rows

def main(path):
    raw=json.loads(path.read_text(encoding='utf-8'))
    seen={canonical_note(x.get('url','')) for x in raw.get('items',[])}
    seen.discard(None)
    collected=[]
    errors=0
    # Rotate one fixed public-index query every half hour; all four in two hours.
    # Polling an index more frequently does not make its content real time.
    now=dt.datetime.now(dt.timezone.utc)
    slot=now.hour*2+(1 if now.minute>=30 else 0)
    chosen=(QUERIES[slot%len(QUERIES)],)
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
    community=[]
    try:
        community=parse_public_issues(public_github_issues(),dt.datetime.now(dt.timezone.utc),seen)
        print(f'XHS public issue contributions: {len(community)} eligible public links',flush=True)
    except Exception as e:
        print('XHS public issue contributions unavailable ('+type(e).__name__+'); '
              'continuing with public index and curated links',flush=True)
    curated=[]
    curated_file=ROOT/'bootstrap/xhs-curated.json'
    try:
        curated=parse_curated(json.loads(curated_file.read_text(encoding='utf-8')),
                              dt.datetime.now(dt.timezone.utc),seen)
    except (OSError,ValueError) as e:
        print('XHS curated link list unavailable: '+type(e).__name__,flush=True)
    raw['items'].extend((collected+community+curated)[:MAX_PER_ROUND])
    path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    print(f'XHS keyless discovery: {len(collected)} indexed; {len(community)} public submissions; {len(curated)} curated; {errors} search-feed failures; '
          'notes may be stale; MiMo review required',flush=True)

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: collect_xhs_index.py candidates.json')
    main(Path(sys.argv[1]))
