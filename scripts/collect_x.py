"""Optional, budget-guarded X recent-search connector.

Only X's official read API is supported: no cookies, browser scraping, proxy
workarounds, Nitter mirrors or unauthorized account access. Credentials are
read only from the GitHub Actions Secret in this process.
"""
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
API="https://api.x.com/2/tweets/search/recent"
STATE=ROOT/"state/x_read_budget.json"
UTC=dt.timezone.utc
MAX_CALLS_PER_DAY=4
MAX_RESULTS=10
MAX_BYTES=160_000
MAX_COST_USD_PER_DAY=MAX_CALLS_PER_DAY*MAX_RESULTS*0.005  # 0.20 USD/day max post reads
# Search syntax is from X's documented recent-search operators.
QUERIES=(
    '("free trial" OR "free credits" OR "promo code" OR "free API") (AI OR Claude OR Gemini OR AWS OR coding) -is:retweet -is:reply',
    '("优惠券" OR "红包" OR "外卖" OR "限免" OR "折扣") (京东 OR 淘宝 OR AI OR 软件) -is:retweet -is:reply',
)
SIGNAL=re.compile(r'free trial|free credits?|promo code|discount|free (?:api|tier|plan)|'
                  r'giveaway|coupon|limited.time|优惠券|红包|外卖|限免|折扣|限时|免费试用|'
                  r'满\d+减\d+|赠送额度',re.I)
SPAM=re.compile(r'\b(?:airdrop|crypto|token presale|referral farming)\b|'
                r'进群|私信领取|共享账号|售卖账号|邀请码交易|代充|抽奖|转发抽取',re.I)
ID=re.compile(r'^[0-9]{6,22}$')

class BlockRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def parse_posts(blob,now):
    if not isinstance(blob,dict) or not isinstance(blob.get("data",[]),list):
        raise ValueError("Unexpected X API JSON")
    entries=blob.get("data",[])
    if len(entries)>MAX_RESULTS:
        raise ValueError("Response exceeds configured X read limit")
    items=[]
    for p in entries:
        if not isinstance(p,dict):continue
        post_id=str(p.get("id") or "")
        text=" ".join(str(p.get("text") or "").split())
        if not ID.fullmatch(post_id) or not (12<=len(text)<=1200):continue
        if not SIGNAL.search(text) or SPAM.search(text):continue
        try:when=dt.datetime.fromisoformat(str(p.get("created_at") or "").replace("Z","+00:00"))
        except ValueError:continue
        if when.tzinfo is None or when>now+dt.timedelta(minutes=10) or when<now-dt.timedelta(days=2):
            continue
        title=re.sub(r'https?://\S+','',text).strip()[:160]
        if len(title)<10:continue
        category="ai" if re.search(r'AI|API|Claude|Gemini|AWS|model|openai|ChatGPT|gpt',title,re.I) else "goods"
        items.append({"source_id":"x-deals","title":title,
            "url":"https://x.com/i/web/status/"+post_id,
            "summary":"X 公开用户发布的促销线索；尚未独立核实资格、价格或实际优惠。"
                      " 原帖可能删除或发生变化，谨防虚假券、引流或冒充官方。",
            "published_at":when.astimezone(UTC).isoformat(timespec="seconds"),
            "expires_at":None,"category":category,"kind":"deal",
            "price":None,"is_free":False,"score":0})
    return items

def load_state():
    try:
        data=json.loads(STATE.read_text(encoding="utf-8"))
        if isinstance(data,dict):return data
    except (OSError,ValueError):pass
    return {}

def save_state(obj):
    STATE.parent.mkdir(parents=True,exist_ok=True)
    tmp=STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(STATE)

def main(path, now=None, opener=None):
    if os.environ.get("X_FETCH_ENABLED")!="true":
        print("X read: not scheduled in this run; no charge",flush=True)
        return
    token=os.environ.get("X_BEARER_TOKEN","").strip()
    if not token:
        print("X read: X_BEARER_TOKEN not configured; connector disabled, no charge",flush=True)
        return
    now=now or dt.datetime.now(UTC)
    date=now.strftime("%Y-%m-%d")
    state=load_state()
    if state.get("utcDate")!=date:state={"utcDate":date,"calls":0,"reservedPostReads":0}
    if int(state.get("calls",0))>=MAX_CALLS_PER_DAY or int(state.get("reservedPostReads",0))+MAX_RESULTS>MAX_CALLS_PER_DAY*MAX_RESULTS:
        print("X read: local daily budget limit reached, no request",flush=True)
        return
    # Each window is 6 hours, and manual retries may not double-bill a window.
    window=now.hour//6
    if int(state.get("lastWindow",-1))==window:
        print("X read: six-hour window already polled, no request",flush=True)
        return
    state["calls"]=int(state.get("calls",0))+1
    state["reservedPostReads"]=int(state.get("reservedPostReads",0))+MAX_RESULTS
    state["lastWindow"]=window
    state["lastAttemptAt"]=now.isoformat(timespec="seconds")
    # Reserve before attempting a billable API read; this state is committed to
    # public repo as counts only (no tokens, post identifiers or personal data).
    save_state(state)
    query=QUERIES[window%len(QUERIES)]
    params=urlencode({"query":query,"max_results":MAX_RESULTS,"tweet.fields":"created_at"})
    req=Request(API+"?"+params,headers={"Authorization":"Bearer "+token,
               "Accept":"application/json","User-Agent":"ResourceRadar/1.0"})
    opener=opener or build_opener(BlockRedirect())
    try:
        with opener.open(req,timeout=15) as res:
            if urlsplit(res.geturl()).hostname!="api.x.com":
                raise ValueError("Unexpected X API host")
            data=res.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES:raise ValueError("Oversized X response")
        posts=parse_posts(json.loads(data),now)
        raw=json.loads(path.read_text(encoding="utf-8"))
        seen={str(x.get("url")) for x in raw.get("items",[])}
        unique=[]
        for p in posts:
            if p["url"] not in seen:
                seen.add(p["url"]);unique.append(p)
        raw["items"].extend(unique)
        path.write_text(json.dumps(raw,ensure_ascii=False),encoding="utf-8")
        print(f"X official API: {len(posts)} relevant posts, {len(unique)} new leads;"
              f" reserved reads today {state['reservedPostReads']}/{MAX_CALLS_PER_DAY*MAX_RESULTS};"
              " all must pass MiMo screening",flush=True)
    except HTTPError as e:
        print(f"X official API unavailable (HTTP {e.code}); other sources unaffected",flush=True)
    except (URLError,OSError,ValueError,KeyError) as e:
        print("X official API unavailable ("+type(e).__name__+"); other sources unaffected",flush=True)

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: collect_x.py candidates.json")
    main(Path(sys.argv[1]))
