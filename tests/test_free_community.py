import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_community import (
    HN_API, PH_FEED, get_public, parse_hn, parse_producthunt,
    MAX_PER_SOURCE, UTC,
)

class FreeCommunityFeeds(unittest.TestCase):
    def test_hacker_news_recent_trial_and_discount_only(self):
        now=dt.datetime(2026,11,25,4,tzinfo=UTC)
        raw={"hits":[
            {"objectID":"45512346","title":"Show HN: Free trial and credits for a developer AI assistant",
             "story_text":"Free credits for new registered accounts.","created_at":"2026-11-25T03:00:00Z"},
            {"objectID":"45512347","title":"Just discussing the best software ideas",
             "story_text":"","created_at":"2026-11-25T03:00:00Z"},
            {"objectID":"45512348","title":"Amazing free trial for an app",
             "story_text":"","created_at":"2026-11-10T03:00:00Z"},
            {"objectID":"ABC---","title":"Free trial for all",
             "story_text":"","created_at":"2026-11-25T03:00:00Z"},
        ]}
        out=parse_hn(json.dumps(raw),now)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["url"],'https://news.ycombinator.com/item?id=45512346')
        self.assertEqual(out[0]["source_id"],'hn-offers')
        self.assertEqual(out[0]["category"],'ai')
    def test_free_developer_tool_is_candidate_not_approved(self):
        from collect_community import eligible
        self.assertTrue(eligible('Free AI tool for coders','Free to use as a developer'))
        self.assertTrue(eligible('Open-source AI coding assistant','Free for independent developers'))
        self.assertFalse(eligible('Just a beautiful notebook app','Nice notes for everyone'))
        self.assertFalse(eligible('Free AI credits in our crypto airdrop','Referral farming'))
    def test_producthunt_atom_promotional_entries_only(self):
        now=dt.datetime(2026,11,25,4,tzinfo=UTC)
        feed='''<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>AI Workspace — Free Pro trial for developers</title>
          <link rel="alternate" href="https://www.producthunt.com/posts/ai-workspace?ref=abc"/>
          <published>2026-11-25T03:30:00Z</published>
          <content type="html">New accounts can try a free plan for one month</content></entry>
        <entry><title>Just a generic daily notebook</title>
          <link href="https://www.producthunt.com/posts/notebook-app"/>
          <published>2026-11-25T03:30:00Z</published></entry>
        <entry><title>Free trial from unknown domain</title>
          <link href="https://evil.example/posts/product"/><published>2026-11-25T03:30:00Z</published></entry>
        </feed>'''
        out=parse_producthunt(feed,now)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['url'],'https://www.producthunt.com/posts/ai-workspace')
        self.assertEqual(out[0]['source_id'],'producthunt-deals')
    def test_no_arbitrary_network_and_bounded_sources(self):
        self.assertRaises(ValueError,get_public,'https://evil.example/rss')
        self.assertRaises(ValueError,get_public,'http://hn.algolia.com/api/v1/search_by_date')
        self.assertRaises(ValueError,get_public,'https://hn.algolia.com/api/v1/search_by_date?url=http%3A%2F%2Flocalhost')
        self.assertRaises(ValueError,get_public,'https://www.producthunt.com/posts/product')
        self.assertLessEqual(MAX_PER_SOURCE,10)
        self.assertEqual(HN_API,'https://hn.algolia.com/api/v1/search_by_date')
        self.assertEqual(PH_FEED,'https://www.producthunt.com/feed')

if __name__=='__main__':unittest.main()
