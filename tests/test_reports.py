import csv
import io
import unittest
from unittest.mock import patch, Mock
from job_monitor.reports import deduplicate, highlights, channel_rows, csv_bytes
from job_monitor.discord import send_report
import run


def row(n, provider='jooble', score=80, location='Cork, Ireland'):
    return ({'id':str(n),'company':'Employer '+str(n),'title':'IT Support',
             'location':location,'url':f'https://example.com/jobs/{n}', 'provider':provider},
            'IT Support / Technical',{'score':score,'experience':'Not stated','description':'Support, systems'})

class Reports(unittest.TestCase):
    def test_complete_csv_and_channel_filters(self):
        rows=[row(i, location='Cork, Ireland' if i<25 else 'Dublin, Ireland') for i in range(40)]
        self.assertEqual(len(list(csv.reader(io.StringIO(csv_bytes(rows).decode('utf-8-sig'))))),41)
        self.assertEqual(len(channel_rows(rows,'local')),25)
        self.assertEqual(channel_rows([row(1,score=74)],'ats'),[])

    def test_direct_duplicate_preferred_tracking_ignored(self):
        a=row(1); b=row(1,'greenhouse'); b[0]['url']+='?utm_source=test'
        self.assertEqual(deduplicate([a,b]),[b])
        c=row(2); c[0]['company']='Other'
        self.assertEqual(len(deduplicate([a,c])),2)

    def test_balanced_highlights_keep_csv_complete(self):
        rows=[row(i) for i in range(20)]+[row(i,'greenhouse',60) for i in range(20,25)]
        picks=highlights(rows)
        self.assertEqual(len(picks),6)
        self.assertEqual(sum(r[0]['provider']=='greenhouse' for r in picks),4)
        self.assertEqual(len(channel_rows(rows,'general')),25)

    def test_formula_and_csv_quoting(self):
        r=row(1);r[0]['company']='=BAD()';r[0]['title']='Support, "IT"'
        values=list(csv.reader(io.StringIO(csv_bytes([r]).decode('utf-8-sig'))))[1]
        self.assertEqual(values[0],"'=BAD()")
        self.assertEqual(values[1],'Support, "IT"')

    @patch('job_monitor.discord.requests.post')
    def test_all_detailed_cards_no_attachments(self, post):
        from job_monitor.discord import embed_size
        post.return_value=Mock(status_code=200)
        send_report('https://example.test',[row(i) for i in range(40)],'local','now',cached=True)
        embeds=[]
        for call in post.call_args_list:
            self.assertNotIn('files',call.kwargs)
            self.assertNotIn('data',call.kwargs)
            payload=call.kwargs['json']
            self.assertLessEqual(len(payload['embeds']),10)
            self.assertLessEqual(sum(embed_size(e) for e in payload['embeds']),6000)
            embeds.extend(payload['embeds'])
        self.assertEqual(len(embeds),40)
        self.assertEqual(len({e['url'] for e in embeds}),40)
        for embed in embeds:
            for label in ('Company','Location','Category','Experience level','Experience requirement','CV fit estimate','Summary','Source','Apply'):
                self.assertIn('**'+label+':**',embed['description'])
        self.assertIn('not been rechecked',post.call_args_list[0].kwargs['json']['content'])

    @patch('job_monitor.discord.requests.post')
    def test_compact_cork_shortlist_has_apply_link(self, post):
        post.return_value=Mock(status_code=200)
        send_report('https://example.test',[row(1),row(2,location='Dublin'),row(3,score=77),row(4,location='Kerry')],'ats','now')
        embeds=post.call_args.kwargs['json']['embeds']
        self.assertEqual(len(embeds),1)
        self.assertIn('**Apply:** [Apply for this job](https://example.com/jobs/1)',embeds[0]['description'])
        self.assertNotIn('**Summary:**',embeds[0]['description'])

    @patch('job_monitor.discord.requests.post')
    def test_empty_feed(self, post):
        post.return_value=Mock(status_code=200)
        send_report('https://example.test',[],'local','now')
        self.assertEqual(post.call_args.kwargs['json']['embeds'],[])
        self.assertIn('0 matching vacancies',post.call_args.kwargs['json']['content'])

    @patch('job_monitor.discord.requests.post')
    def test_rate_limit_retries_same_json(self, post):
        post.side_effect=[Mock(status_code=429,json=lambda:{'retry_after':.5}),Mock(status_code=200)]
        with patch('job_monitor.discord.time.sleep'):
            send_report('https://example.test',[row(1)],'general','now')
        self.assertEqual(post.call_count,2)
        self.assertEqual(post.call_args_list[0],post.call_args_list[1])

    @patch.object(run, 'report', return_value=0)
    @patch.object(run, 'load_state')
    def test_saved_report_never_collects(self, state, report):
        j,c,a=row(1)
        state.return_value={'last_scan_utc':'yesterday','job_index':{'1':dict(j,category=c,fit_score=80)}}
        with patch.object(run,'collect') as collect:
            self.assertEqual(run.saved_report('local',True),0)
            collect.assert_not_called()
        self.assertTrue(report.call_args.kwargs['cached'])

    @patch.object(run, 'write_state')
    @patch.object(run, 'report', return_value=0)
    def test_fresh_report_includes_seen_and_does_not_change_history(self, report, write):
        j,c,a=row(1,'greenhouse')
        j['description']='Technical support'
        with patch.object(run,'load_sources',return_value=[{'provider':'greenhouse','slug':'test','company':'Test'}]), \
             patch.object(run,'load_state',return_value={'initialized':True,'seen':{'1':'old'},'baselined_sources':[]}), \
             patch.object(run,'collect',return_value=([j],[],{'greenhouse:test'})), \
             patch.object(run,'session_with_retries',return_value=None):
            self.assertEqual(run.scan(full_report=True,channel='all'),0)
        self.assertEqual(len(report.call_args.args[0]),1)
        write.assert_not_called()

