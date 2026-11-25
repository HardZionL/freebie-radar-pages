import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_xhs_index import canonical_note,parse_feed,public_bing_rss,clean_title,QUERIES,parse_curated,parse_public_issues,public_github_issues,ISSUE_TITLE_PREFIX

def rss(items):
    return '<rss version="2.0"><channel><title>Bing</title>'+items+'</channel></rss>'
class PublicXhsIndex(unittest.TestCase):
    def test_only_canonical_public_note_links(self):
        note='681a0a8b000000002102f720'
        self.assertEqual(canonical_note('https://www.xiaohongshu.com/explore/'+note+'?xsec_token=secret'),
                         'https://www.xiaohongshu.com/explore/'+note)
        self.assertEqual(canonical_note('https://xiaohongshu.com/discovery/item/'+note),
                         'https://www.xiaohongshu.com/explore/'+note)
        for link in ('https://xiaohongshu.com.evil.example/explore/'+note,
                     'http://www.xiaohongshu.com/explore/'+note,
                     'https://xhslink.com/a/something',
                     'https://www.xiaohongshu.com/search_result?keyword=红包',
                     'https://www.xiaohongshu.com/user/profile/'+note,
                     'https://www.xiaohongshu.com/explore/'+note+'/extra',
                     'https://www.xiaohongshu.com/explore/../../admin'):
            self.assertIsNone(canonical_note(link))
    def test_filters_unsafe_and_duplicate_notes(self):
        a='681a0a8b000000002102f720';b='681a0a8b000000002102f721'
        xml=rss(f'''<item><title>美团外卖满29减15红包天天领</title>
        <link>https://www.xiaohongshu.com/explore/{a}</link>
        <pubDate>Wed, 25 Nov 2026 04:00:00 GMT</pubDate></item>
        <item><title>美团外卖满29减15红包天天领</title><link>https://www.xiaohongshu.com/explore/{a}?foo=1</link></item>
        <item><title>领取超值抽奖优惠券请私信扫码</title><link>https://www.xiaohongshu.com/explore/{b}</link></item>
        <item><title>普通生活记录没有任何优惠信息</title><link>https://www.xiaohongshu.com/explore/{b}</link></item>
        <item><title>平台满减券今夜可领</title><link>https://notxiaohongshu.com/explore/{b}</link></item>''')
        rows=parse_feed(xml)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_id'],'xhs-public-index')
        self.assertIsNone(rows[0]['published_at'])
        self.assertTrue(rows[0]['url'].endswith(a))
        self.assertNotIn('secret',str(rows))
    def test_rejects_html_challenges_and_unapproved_query(self):
        with self.assertRaises(ValueError):parse_feed('<html><body>captcha</body></html>')
        with self.assertRaises(ValueError):public_bing_rss('user controlled query')
        self.assertEqual(len(QUERIES),4)
    def test_admin_curated_links_are_screened_and_time_bounded(self):
        import datetime as dt
        note='681a0a8b000000002102f720'
        now=dt.datetime(2026,11,25,tzinfo=dt.timezone.utc)
        good='https://www.xiaohongshu.com/explore/'+note+'?tracking=user'
        rows=parse_curated([
            {'url':good,'title':'美团外卖满29减15红包领取指南','addedOn':'2026-11-25'},
            {'url':good,'title':'美团外卖满29减15红包领取指南','addedOn':'2026-11-25'},
            {'url':'https://evil.example/explore/'+note,'title':'红包券大额','addedOn':'2026-11-25'},
            {'url':good,'title':'红包天天领私信联系我','addedOn':'2026-11-25'},
            {'url':good,'title':'美团外卖券促销','addedOn':'2026-10-01'},
        ],now,set())
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_id'],'xhs-curated')
        self.assertIsNone(rows[0]['published_at'])
        self.assertEqual(rows[0]['url'],'https://www.xiaohongshu.com/explore/'+note)
    def test_public_github_issues_are_just_safe_public_note_leads(self):
        import datetime as dt
        now=dt.datetime(2026,11,25,6,tzinfo=dt.timezone.utc)
        note='681a0a8b000000002102f720'
        correct='https://www.xiaohongshu.com/explore/'+note
        items=[
            dict(title=ISSUE_TITLE_PREFIX+' 美团外卖满29减15红包领取方法',
                 body='### 公开笔记链接\\n'+correct+'?xsec_token=private',
                 created_at='2026-11-25T05:00:00Z',state='open',user={'login':'private-user'}),
            dict(title=ISSUE_TITLE_PREFIX+' 美团外卖满29减15红包领取方法',
                 body=correct,created_at='2026-11-25T05:00:00Z',state='open'),
            dict(title=ISSUE_TITLE_PREFIX+' 请私信联系领取外卖红包',
                 body='https://www.xiaohongshu.com/explore/681a0a8b000000002102f721',
                 created_at='2026-11-25T05:00:00Z',state='open'),
            dict(title='[其他讨论] 美团外卖红包',
                 body=correct,created_at='2026-11-25T05:00:00Z',state='open'),
            dict(title=ISSUE_TITLE_PREFIX+' 外卖红包优惠券',
                 body='https://fake-xiaohongshu.com/explore/681a0a8b000000002102f722',
                 created_at='2026-11-25T05:00:00Z',state='open'),
            dict(title=ISSUE_TITLE_PREFIX+' 平台通用外卖优惠券',
                 body='https://www.xiaohongshu.com/explore/681a0a8b000000002102f722',
                 created_at='2026-11-01T05:00:00Z',state='open'),
            dict(title=ISSUE_TITLE_PREFIX+' 平台通用外卖优惠券',
                 body='https://www.xiaohongshu.com/explore/681a0a8b000000002102f723',
                 created_at='2026-11-25T05:00:00Z',state='open',pull_request={'url':'test'})
        ]
        got=parse_public_issues(items,now,set())
        self.assertEqual(len(got),1)
        self.assertEqual(got[0]['source_id'],'xhs-community')
        self.assertEqual(got[0]['url'],correct)
        self.assertIsNone(got[0]['published_at'])
        self.assertNotIn('private-user',str(got))
        self.assertNotIn('xsec_token',str(got))
        self.assertRaises(ValueError,parse_public_issues,{},now,set())
    def test_public_github_issues_is_read_only_fixed_endpoint(self):
        from collect_xhs_index import GITHUB_ISSUES
        self.assertEqual(GITHUB_ISSUES,'https://api.github.com/repos/HardZionL/freebie-radar-pages/issues?state=open&per_page=30')
        self.assertNotIn('token',GITHUB_ISSUES)
    def test_title_cleanup(self):
        self.assertEqual(clean_title('福利券今晚领取 - 小红书'),'福利券今晚领取')
if __name__=='__main__':unittest.main()
