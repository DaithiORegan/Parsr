import unittest
from job_monitor.routing import eligible_for_channel, is_cork, channel_threshold, target_webhooks
class RoutingTests(unittest.TestCase):
    def test_cork_only(self):
        for loc in ('County Cork, Ireland','Little Island, Cork','Cobh'):
            self.assertTrue(is_cork({'location':loc}))
        for loc in ('Tralee','Killarney, Kerry','Remote - Ireland','Dublin'):
            self.assertFalse(is_cork({'location':loc,'description':'Work with Cork clients'}))
    def test_ats_boundary(self):
        self.assertTrue(eligible_for_channel('ats',{'location':'Cork'}, {'score':78,'experience_years':2}))
        for a in ({'score':77},{'score':90,'experience_years':3},{'score':90,'experience':'3+ years mentioned (check advert)'},{'score':90,'level':'Senior / leadership'}):
            self.assertFalse(eligible_for_channel('ats',{'location':'Cork'},a))
        self.assertFalse(eligible_for_channel('ats',{'location':'Dublin'},{'score':99}))
        self.assertEqual(channel_threshold('ats',{}),78)
    def test_all_jobs_in_general_and_local(self):
        self.assertTrue(eligible_for_channel('local',{'location':'Cork'},{'score':10}))
        self.assertEqual(channel_threshold('general',{}),0)
        self.assertEqual(channel_threshold('local',{}),0)
    def test_duplicate_webhooks_rejected(self):
        with self.assertRaises(ValueError):
            target_webhooks({'DISCORD_WEBHOOK_URL':'https://example.com/h','DISCORD_WEBHOOK_LOCAL':'https://example.com/h'})
