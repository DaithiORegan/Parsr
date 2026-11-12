import unittest
from scripts.export_web import export
class WebExport(unittest.TestCase):
    def test_full_descriptions_categories_and_untrusted_urls(self):
        s={'last_scan_utc':'2026-11-12T10:17:00Z','job_index':{
            'a':{'title':'Data Analyst','category':'IT Support / Technical','url':'https://example.com/job','full_description':'<p>SQL required</p>'},
            'b':{'title':'SOC Analyst','category':'Cybersecurity','url':'https://example.com/b','description':'Short snippet'},
            'bad':{'title':'Unsafe','url':'javascript:alert(1)'}}}
        data=export(s);self.assertEqual(len(data['jobs']),2)
        a,b=data['jobs'];self.assertEqual(a['category'],'Analyst');self.assertEqual(a['description'],'SQL required');self.assertTrue(a['description_complete'])
        self.assertEqual(b['category'],'Cybersecurity');self.assertFalse(b['description_complete'])

    def test_latest_scan_marker_separates_historic_records(self):
        s={'last_scan_utc':'2026-11-12T10:17:00+00:00','job_index':{
            'fresh':{'url':'https://example.com/a','last_seen':'2026-11-12T10:16:59+00:00'},
            'old':{'url':'https://example.com/b','last_seen':'2026-11-11T10:17:00+00:00'}}}
        jobs=export(s)['jobs']
        self.assertTrue(jobs[0]['seen_in_latest_scan'])
        self.assertFalse(jobs[1]['seen_in_latest_scan'])

    def test_encoded_html_becomes_readable_paragraphs_and_bullets(self):
        from scripts.export_web import readable_text
        value='&lt;p&gt;About the role&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Support users&lt;/li&gt;&lt;li&gt;Document fixes&lt;/li&gt;&lt;/ul&gt;'
        text=readable_text(value)
        self.assertIn('About the role\n',text)
        self.assertIn('• Support users',text)
        self.assertNotIn('<p>',text)
        self.assertNotIn('&lt;',text)

    def test_failed_sources_keep_prior_listings_and_report_coverage(self):
        state={'last_scan_utc':'2026-11-12T10:17:00+00:00', 'scan_health':{'failed_sources':[{'provider':'irishjobs','company':'IrishJobs'}]}, 'job_index':{
            'old':{'url':'https://example.com/old','title':'Security Analyst','location':'Cork','provider':'irishjobs','full_description':'Snippet only','last_seen':'2026-11-11T10:17:00+00:00'}}}
        data=export(state)
        self.assertEqual(len(data['jobs']),1)
        self.assertEqual(data['jobs'][0]['availability'],'unconfirmed')
        self.assertFalse(data['jobs'][0]['description_complete'])
        self.assertEqual(data['scan_health']['failed_sources'][0]['provider'],'irishjobs')
