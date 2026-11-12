import unittest
from scripts.import_public_feed import merge_feed
class PublicFeed(unittest.TestCase):
    def test_public_jobs_merge_without_replacing_private_state(self):
        state={'last_scan_utc':'2026-11-12T10:00:00Z','seen':{'delivered':'old'},'job_index':{'old':{'title':'Retained'}}}
        feed={'scanned_at':'2026-11-12T12:00:00Z','scan_health':{'locked_sources':[]},'jobs':[{'id':'new','url':'https://example.com/job','title':'Support','cv_text':'must not transfer','fit_score':99}]}
        result,changed=merge_feed(state,feed)
        self.assertTrue(changed);self.assertIn('old',result['job_index']);self.assertIn('new',result['job_index'])
        self.assertEqual(result['seen'],state['seen']);self.assertNotIn('cv_text',result['job_index']['new']);self.assertNotIn('fit_score',result['job_index']['new'])
        self.assertEqual(result['scan_health'],feed['scan_health'])
    def test_older_snapshot_cannot_replace_newer_data(self):
        state={'last_scan_utc':'2026-11-12T12:00:00Z','job_index':{}}
        result,changed=merge_feed(state,{'scanned_at':'2026-11-12T10:00:00Z','jobs':[]})
        self.assertFalse(changed);self.assertEqual(result,state)

    def test_first_index_time_survives_public_to_live_sync(self):
        timestamp='2026-11-12T23:00:00Z'
        feed={'scanned_at':timestamp,'jobs':[{'id':'new','url':'https://example.com/job','first_indexed_at':timestamp}]}
        result,_=merge_feed({'job_index':{}},feed)
        self.assertEqual(result['job_index']['new']['first_indexed_at'],timestamp)
