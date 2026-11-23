import datetime as dt
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_official_ai import DOCS,FEEDS,PROMO,parse_rss,quick_trial_is_confirmed,safe_blog_link,UTC

class OfficialOffers(unittest.TestCase):
    def test_aws_trial_confirmation_only_from_explicit_language(self):
        body='<html><body><h1>AWS Quick plans and pricing</h1><p>New accounts receive 30 days of Plus at no cost.</p></body></html>'
        self.assertTrue(quick_trial_is_confirmed(body))
        self.assertFalse(quick_trial_is_confirmed('<p>Claude Opus 5.5 free forever</p>'))
        self.assertFalse(quick_trial_is_confirmed('<p>Quick Plus is available at a monthly price.</p>'))
    def test_first_party_rss_only_and_real_freshness(self):
        now=dt.datetime(2026,11,23,tzinfo=UTC)
        rss='''<rss><channel>
          <item><title>AWS Quick free trial for new users</title>
          <link>https://aws.amazon.com/blogs/aws/quick-offer/?a=1</link>
          <pubDate>Mon, 23 Nov 2026 08:00:00 +0000</pubDate>
          <description>New users receive an optional free trial.</description></item>
          <item><title>AWS Quick new feature</title>
          <link>https://evil.example/blogs/aws/quick</link>
          <pubDate>Mon, 23 Nov 2026 08:00:00 +0000</pubDate></item>
          <item><title>AWS Quick free credits</title>
          <link>https://aws.amazon.com/blogs/aws/old/</link>
          <pubDate>Mon, 02 Nov 2026 08:00:00 +0000</pubDate></item>
        </channel></rss>'''
        items=parse_rss(rss,now)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['source_id'],'aws-official-ai')
        self.assertEqual(items[0]['url'],'https://aws.amazon.com/blogs/aws/quick-offer/')
        self.assertTrue(items[0]['published_at'].startswith('2026-11-23'))
    def test_host_is_strictly_constrained(self):
        self.assertIsNone(safe_blog_link('https://aws.amazon.com.evil.com/blogs/quick'))
        self.assertIsNone(safe_blog_link('https://evil.com/blogs/quick'))
        self.assertIsNone(safe_blog_link('https://127.0.0.1/blogs/quick'))
        self.assertIsNone(safe_blog_link('javascript:alert(1)'))
        self.assertIsNone(safe_blog_link('https://aws.amazon.com/quick/pricing/'))
        self.assertEqual(safe_blog_link('https://aws.amazon.com/blogs/aws/offer/?track=1'),
                         'https://aws.amazon.com/blogs/aws/offer/')
    def test_official_seed_truthful_without_model_claim(self):
        seed=json.loads((Path(__file__).resolve().parents[1]/'scripts/official-benefits.json').read_text())
        self.assertEqual(seed[0]['url'],DOCS)
        self.assertEqual(seed[0]['reviewStatus'],'official-confirmed')
        self.assertEqual(seed[0]['quality'],0)
        self.assertIn('30 天',seed[0]['title'])
        self.assertIn('尚无官方',seed[0]['reason'])
        self.assertEqual(len(FEEDS),3)
        self.assertTrue(PROMO.search('new free trial'))

if __name__=='__main__':unittest.main()
