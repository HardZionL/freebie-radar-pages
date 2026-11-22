import unittest, sys, datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review import candidate,safe_url,select_daily,iso,UTC,clean
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
    def test_quota(self):
        now=dt.datetime.now(UTC); items=[]
        for b in ['ai','shopping','media','other']:
            for i in range(10):items.append(dict(id=f'{b}{i}',title=f'{b}{i}',bucket=b,quality=5,firstSeen=iso(now),expires=None))
        out=select_daily(items,[],'2026-11-22',now)
        self.assertEqual(len(out),12)
        self.assertEqual(sum(x['bucket']=='media' for x in out),3)
        self.assertFalse(set(x['id'] for x in out)&set(x['id'] for x in select_daily(items,[{'date':'2026-11-21','items':out}],'2026-11-22',now)))
if __name__=='__main__':unittest.main()
