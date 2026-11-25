import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_x as x

class OfficialXCollector(unittest.TestCase):
    def test_only_public_recent_posts_with_promotional_evidence(self):
        now=dt.datetime(2026,11,25,4,tzinfo=dt.timezone.utc)
        sample={"data":[
            {"id":"1998199819981998","text":"AWS offers free trial credits for eligible new users, check the rules","created_at":"2026-11-25T02:00:00Z"},
            {"id":"1998199819981999","text":"Wonderful rainy day and nothing else","created_at":"2026-11-25T02:00:00Z"},
            {"id":"1998199819982000","text":"giveaway: share our referral farming crypto airdrop promo code","created_at":"2026-11-25T02:00:00Z"},
            {"id":"1998199819982001","text":"美团外卖红包有领取入口但请核实参与条件，优惠券测试","created_at":"2026-11-22T02:00:00Z"},
        ]}
        out=x.parse_posts(sample,now)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["url"],"https://x.com/i/web/status/1998199819981998")
        self.assertNotIn("Bearer",json.dumps(out))
        self.assertEqual(out[0]["source_id"],"x-deals")
    def test_rejects_path_and_size_tricks(self):
        now=dt.datetime(2026,11,25,tzinfo=dt.timezone.utc)
        rows={"data":[{"id":"123/../456","text":"Free trial for AI","created_at":now.isoformat()}]}
        self.assertEqual(x.parse_posts(rows,now),[])
        self.assertRaises(ValueError,x.parse_posts,{"data":[{}]*11},now)
    def test_no_secret_means_no_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"candidates.json";p.write_text('{"items":[]}')
            with patch.dict(os.environ,{"X_FETCH_ENABLED":"true","X_BEARER_TOKEN":""}):
                x.main(p,now=dt.datetime(2026,11,25,tzinfo=dt.timezone.utc))
            self.assertEqual(json.loads(p.read_text()),{"items":[]})
    def test_daily_budget_formula(self):
        self.assertEqual(x.MAX_RESULTS,10)
        self.assertEqual(x.MAX_CALLS_PER_DAY,4)
        self.assertEqual(x.MAX_COST_USD_PER_DAY,0.20)
        self.assertEqual(len(x.QUERIES),2)

if __name__=="__main__":unittest.main()
