import unittest, sys, datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review import candidate,safe_url,select_daily,iso,UTC,clean,bucket_hint,shopping_lead,offer_type,shortlist
from collect_coupons import canonical,parse_page
class TestRadar(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(safe_url('https://www.smzdm.com/p/123/?token=secret#x','rss-smzdm'),'https://www.smzdm.com/p/123/')
        for u in ('javascript:alert(1)','https://smzdm.com.evil.test/a','https://x@smzdm.com/a','https://127.0.0.1/a','https://go.smzdm.com/a'):
            self.assertIsNone(safe_url(u,'rss-smzdm'))
    def test_candidate(self):
        now=dt.datetime.now(UTC)
        r=dict(source_id='rss-smzdm',url='https://www.smzdm.com/p/123/',title='腾讯视频年卡优惠',summary='测试',published_at=iso(now),category='media',price=88)
        self.assertEqual(candidate(r,now)['hint'],'media')
        self.assertIsNone(candidate(dict(r,title='账号出售'),now))
        self.assertIsNone(candidate(dict(r,expires_at=iso(now-dt.timedelta(days=1))),now))
        self.assertIn('[已隐藏]',clean('api key sk-12345678901234567',100))
    def test_shopping_source_priority(self):
        self.assertEqual(bucket_hint({'title':'某品牌耳机 199 元', 'source':'rss-smzdm', 'category':'other'}),'shopping')
        self.assertEqual(bucket_hint({'title':'LEGO holiday deal', 'source':'rss-9to5toys', 'category':'other'}),'shopping')
        self.assertEqual(bucket_hint({'title':'腾讯视频会员 5 折', 'source':'rss-smzdm', 'category':'other'}),'media')
    def test_unverified_shopping_lead_is_distinct_and_safe(self):
        now=dt.datetime.now(UTC)
        r=dict(source_id='rss-smzdm',url='https://www.smzdm.com/p/12345/',title='京东商城 电水壶 59.9元（需用券）',summary='无',published_at=iso(now))
        x=shopping_lead(r,now)
        self.assertIsNotNone(x)
        self.assertEqual(x['reviewStatus'],'unverified')
        self.assertEqual(x['quality'],0)
        self.assertEqual(x['bucket'],'shopping')
        self.assertIsNone(shopping_lead(dict(r,title='某款商品普通介绍，无价格'),now))
        self.assertIsNone(shopping_lead(dict(r,url='https://post.smzdm.com/p/a12345/'),now))
        self.assertIsNone(shopping_lead(dict(r,url='https://evil.invalid/p/12345/'),now))
        self.assertIsNone(shopping_lead(dict(r,source_id='rss-9to5toys'),now))
        self.assertIsNone(shopping_lead(dict(r,published_at=iso(now-dt.timedelta(days=9))),now))
    def test_seven_day_horizon(self):
        now=dt.datetime.now(UTC)
        r=dict(source_id='rss-smzdm',url='https://www.smzdm.com/p/987/',title='视频会员七天优惠',summary='活动',category='media',published_at=iso(now-dt.timedelta(days=5)))
        self.assertIsNotNone(candidate(r,now))
        self.assertIsNone(candidate(dict(r,published_at=iso(now-dt.timedelta(days=9))),now))
    def test_coupon_regex_never_matches_empty(self):
        from collect_coupons import BLOCK
        self.assertIsNone(BLOCK.search(''))
        self.assertIsNone(BLOCK.search('美团外卖满29-14元优惠券'))
    def test_coupon_source_parser(self):
        html='''<a href="https://m.smzdm.com/p/174492951/?utm_source=x">
          美团外卖 满29-14元优惠券天天领</a>
          <a href="https://evil.example/p/174492952">红包20元</a>
          <a href="https://www.smzdm.com/p/123456789">普通测评文章</a>'''
        rows=parse_page(html,'https://m.smzdm.com/lanmu/a21qz15/','rss-smzdm-delivery')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['url'],'https://www.smzdm.com/p/174492951')
        self.assertIsNone(rows[0]['published_at'])
        self.assertEqual(rows[0]['source_id'],'rss-smzdm-delivery')
        self.assertIsNone(canonical('https://evil.example/p/174492951','https://m.smzdm.com/'))
    def test_coupon_prioritized_but_not_autoapproved(self):
        self.assertEqual(offer_type('美团外卖 满30-15 领券'),'delivery')
        self.assertEqual(offer_type('京东 2元无门槛立减券'),'coupon')
        self.assertEqual(offer_type('平台 红包天天领'),'redpacket')
        self.assertEqual(offer_type('蓝牙耳机 89元需用券'),'product')
        now=dt.datetime.now(UTC)
        candidates={}
        for i in range(24):
            src='rss-smzdm-coupon' if i<8 else 'rss-smzdm'
            title='美团外卖满30-15红包'+str(i) if i<8 else '数码好价'+str(i)
            row={'id':str(i),'title':title,'source':src,'hint':'shopping',
                 'offerType':offer_type(title),'published':iso(now),'fingerprint':str(i)}
            candidates[row['id']]=row
        selected=shortlist(candidates,24)
        self.assertEqual(len(selected),24)
        self.assertEqual(len({x['id'] for x in selected}),24)
        self.assertTrue(all(x['offerType']!='product' for x in selected[:8]))
    def test_30_minute_review_stays_balanced(self):
        now=dt.datetime.now(UTC)
        entries={}
        for idx in range(8):
            title=f'外卖优惠券领券优惠{idx}'
            entries['coupon'+str(idx)]=dict(id='coupon'+str(idx),title=title,
                 source='rss-smzdm-coupon',hint='shopping',offerType='delivery',
                 published=iso(now),fingerprint='c'+str(idx))
        for kind in ('ai','shopping','media','other'):
            for idx in range(6):
                src='hn-offers' if kind=='ai' and idx==0 else 'rss-meta-appinn'
                t=dict(id=kind+str(idx),title=kind+' promotion',
                    source=src,hint=kind,offerType='product',
                    published=iso(now),fingerprint=kind+str(idx))
                entries[t['id']]=t
        selected=shortlist(entries,6)
        self.assertEqual(len(selected),6)
        self.assertEqual(len({x['id'] for x in selected}),6)
        self.assertEqual(sum(x['offerType']=='delivery' for x in selected),2)
        self.assertGreaterEqual(sum(x['hint']=='ai' for x in selected),2)
        self.assertGreaterEqual(sum(x['hint']=='media' for x in selected),1)
    def test_xhs_index_links_are_strict_and_deeplinks_cleaned(self):
        n='681a0a8b000000002102f720'
        target='https://www.xiaohongshu.com/explore/'+n
        self.assertEqual(safe_url(target+'?xsec_token=redacted','xhs-public-index'),target)
        self.assertEqual(safe_url('https://xiaohongshu.com/explore/'+n,'xhs-public-index'),target)
        for invalid in ('http://www.xiaohongshu.com/explore/'+n,
                        'https://www.xiaohongshu.com/search_result?query=优惠券',
                        'https://login.xiaohongshu.com/explore/'+n,
                        'https://evil.example/explore/'+n):
            self.assertIsNone(safe_url(invalid,'xhs-public-index'))
    def test_free_community_source_links_are_strict(self):
        self.assertEqual(safe_url('https://news.ycombinator.com/item?id=45123456','hn-offers'),
                         'https://news.ycombinator.com/item?id=45123456')
        for url in ('https://news.ycombinator.com/item?id=45123456&to=evil',
                    'https://news.ycombinator.com.attacker.example/item?id=45123456',
                    'https://evil.example/item?id=45123456','http://news.ycombinator.com/item?id=45123456',
                    'https://news.ycombinator.com/item?id=../secret'):
            self.assertIsNone(safe_url(url,'hn-offers'))
        self.assertEqual(safe_url('https://www.producthunt.com/posts/amazing-ai-deals?ref=x','producthunt-deals'),
                         'https://www.producthunt.com/posts/amazing-ai-deals')
        self.assertIsNone(safe_url('https://evil.example/posts/amazing-ai-deals','producthunt-deals'))
        self.assertIsNone(safe_url('https://x.com/i/web/status/1998199819981998','x-deals'))
    def test_12_item_round_guarantees_ai_and_media_slots(self):
        now=dt.datetime.now(UTC); entries={}
        for kind in ('ai','shopping','media','other'):
            for idx in range(12):
                title=('某券领券免费外卖红包'+str(idx) if kind=='shopping' and idx<9 else kind+' '+str(idx))
                row=dict(id=kind+str(idx),title=title,source='rss-smzdm',
                         hint=kind,offerType='delivery' if kind=='shopping' and idx<9 else 'product',
                         published=iso(now),fingerprint=kind+str(idx))
                entries[row['id']]=row
        out=shortlist(entries,12)
        self.assertEqual(len(out),12)
        self.assertEqual(sum(x['offerType']=='delivery' for x in out),4)
        self.assertGreaterEqual(sum(x['hint']=='ai' for x in out),4)
        self.assertGreaterEqual(sum(x['hint']=='media' for x in out),2)
        self.assertTrue(any(x['hint']=='shopping' and x['offerType']=='product' for x in out))
    def test_review_format_retry_is_bounded(self):
        from unittest.mock import patch
        import review
        batch=[{'title':'Test 1','summary':'trial'}]
        calls=[]
        def fake(b,k,m,max_tokens=0):
            calls.append(max_tokens)
            if len(calls)==1:raise ValueError('invalid JSON format')
            return {0:(True,4,'ai','free')}
        with patch.object(review,'request_review',side_effect=fake):
            self.assertEqual(review.review_with_retry(batch,'dummy','mimo'),{0:(True,4,'ai','free')})
        self.assertEqual(calls,[1050,1600])
    def test_quota(self):
        now=dt.datetime.now(UTC); items=[]
        for b in ['ai','shopping','media','other']:
            for i in range(10):items.append(dict(id=f'{b}{i}',title=f'{b}{i}',bucket=b,quality=5,firstSeen=iso(now),expires=None))
        out=select_daily(items,[],'2026-11-22',now)
        self.assertEqual(len(out),12)
        self.assertEqual(sum(x['bucket']=='media' for x in out),3)
        self.assertFalse(set(x['id'] for x in out)&set(x['id'] for x in select_daily(items,[{'date':'2026-11-21','items':out}],'2026-11-22',now)))
    def test_quota_fill_from_available_categories(self):
        now=dt.datetime.now(UTC)
        items=[dict(id=f'ai{i}',title=f'独立活动ai{i}',bucket='ai',quality=5,firstSeen=iso(now),expires=None) for i in range(22)]
        out=select_daily(items,[],'2026-11-22',now)
        self.assertEqual(len(out),12)
        self.assertEqual(len(set(x['id'] for x in out)),12)
if __name__=='__main__':unittest.main()
