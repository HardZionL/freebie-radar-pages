"""Read-only extraction of coupon and delivery links from two known public pages.

No accounts, cookies, offsite redirects, personalization, or claims of verified
prices. Only canonical public smzdm article links are retained. A failed page
request is non-fatal; the original RSS collectors continue to work.
"""
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

PAGES = {
    'rss-smzdm-coupon': 'https://h5.smzdm.com/user/coupon/coupon_list/',
    'rss-smzdm-delivery': 'https://m.smzdm.com/lanmu/a21qz15/',
}
SIGNAL = re.compile(
    r'红包|无门槛|满\s*\d+\s*(?:减|-|—)\s*\d+|优惠券|代金券|抵扣券|'
    r'立减券|领券|券包|神券|外卖|餐饮券|返现|\d+(?:\.\d+)?\s*折|'
    r'折扣|补贴|京豆|淘金币|返券|买一送一|免费领', re.I)
BLOCK = re.compile(r'抽奖|求购|拼车|返佣|进群|私信|代充|共享账号|账号出售')
ARTICLE = re.compile(r'^/p/(\d{5,12})/?$')
MAX_BYTES = 1_000_000
MAX_TOTAL = 32
MAX_PER_PAGE = 18

class SameProviderRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != 'https' or parts.hostname not in {
            'h5.smzdm.com','m.smzdm.com','www.smzdm.com'
        }:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = None
        self.entries = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.active = [dict(attrs).get('href') or '', []]
    def handle_data(self, text):
        if self.active is not None:
            self.active[1].append(text)
    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.entries.append((self.active[0], ' '.join(self.active[1])))
            self.active = None

def canonical(href, page):
    try:
        parsed = urlsplit(urljoin(page, href))
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            return None
        if parsed.hostname not in {'www.smzdm.com','m.smzdm.com','faxian.smzdm.com',
                                   'h5.smzdm.com'}:
            return None
        m = ARTICLE.fullmatch(parsed.path)
        return 'https://www.smzdm.com/p/' + m[1] if m else None
    except (TypeError, ValueError):
        return None

def parse_page(html, page, source):
    parser = Anchors()
    parser.feed(html)
    found = {}
    for href, text in parser.entries:
        url = canonical(href, page)
        if not url:
            continue
        title = unicodedata.normalize('NFKC', ' '.join(text.split()))
        if len(title) < 8 or len(title) > 220 or BLOCK.search(title):
            continue
        if not SIGNAL.search(title):
            continue
        if url not in found or len(title) > len(found[url]['title']):
            found[url] = {
                'source_id': source, 'title': title[:180], 'url': url,
                'summary': '来自公开优惠券/餐饮外卖频道，券额、领取限制及有效期必须以原网页核对',
                'published_at': None, 'expires_at': None,
                'category': 'goods', 'kind': 'deal', 'price': None,
                'is_free': False, 'score': 0,
            }
        if len(found) >= MAX_PER_PAGE:
            break
    return list(found.values())

def fetch_public_page(url):
    req = Request(url, headers={
        'User-Agent': 'ResourceRadar/1.0 (+https://github.com/HardZionL/freebie-radar-pages)',
        'Accept': 'text/html',
    })
    with build_opener(SameProviderRedirect()).open(req, timeout=12) as res:
        final = urlsplit(res.geturl())
        if final.scheme != 'https' or final.hostname not in {'h5.smzdm.com','m.smzdm.com','www.smzdm.com'}:
            raise ValueError('Unexpected final host')
        if 'text/html' not in res.headers.get('Content-Type',''):
            raise ValueError('Not HTML')
        data = res.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Page too large')
        return data.decode('utf-8', errors='replace')

def main(path):
    raw = json.loads(path.read_text(encoding='utf-8'))
    existing = {x.get('url') for x in raw.get('items', [])}
    added = []
    for source, page in PAGES.items():
        try:
            offers = parse_page(fetch_public_page(page), page, source)
            count = 0
            for offer in offers:
                if offer['url'] in existing:
                    continue
                existing.add(offer['url'])
                added.append(offer)
                count += 1
                if len(added) >= MAX_TOTAL:
                    break
            print(f'{source}: {len(offers)} eligible public offer titles, {count} added',flush=True)
        except Exception as e:
            print(f'{source}: unavailable ({type(e).__name__}: {str(e)[:90]}); continuing with RSS',flush=True)
    raw['items'].extend(added)
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
    print(f'Coupon and delivery candidate enrichment: {len(added)} items; no AI keys used',flush=True)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: coupon_collect.py candidates.json')
    main(Path(sys.argv[1]))
