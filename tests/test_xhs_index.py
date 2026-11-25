import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_xhs_index import canonical_note,parse_feed,public_bing_rss,clean_title,QUERIES

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
    def test_title_cleanup(self):
        self.assertEqual(clean_title('福利券今晚领取 - 小红书'),'福利券今晚领取')
if __name__=='__main__':unittest.main()
