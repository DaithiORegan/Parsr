import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from job_monitor.delivery import delivered,mark,migrate
from job_monitor.reports import deduplicate
from job_monitor.discord import send_report
from job_monitor.bot_store import Store,jobs_from_embeds
from test_reports import row
import run

class Delivery(unittest.TestCase):
    def test_history_is_per_channel_and_survives_changed_source_url(self):
        job=row(1)[0];state={};mark(state,'ats',[job])
        changed=dict(job,url='https://another.example/jobs/123?utm_source=feed',provider='greenhouse')
        self.assertTrue(delivered(state,'ats',changed))
        self.assertFalse(delivered(state,'local',changed))
    def test_tracking_query_ignored(self):
        job=row(1)[0];state={};mark(state,'general',[job])
        changed=dict(job,url=job['url']+'?utm_source=other',company='unknown')
        self.assertTrue(delivered(state,'general',changed))
    def test_same_provider_duplicate_dropped(self):
        a=row(1);b=row(2);b[0].update(company=a[0]['company'])
        self.assertEqual(len(deduplicate([a,b])),1)
    def test_migration_does_not_replay_index_and_does_not_seed_future_jobs(self):
        j,c,a=row(1)
        state={'job_index':{'1':dict(j,fit_score=80,category=c)}}
        migrate(state)
        self.assertTrue(delivered(state,'ats',j))
        self.assertFalse(delivered(state,'ats',row(2)[0]))
        self.assertEqual(migrate(state),state)
    @patch('job_monitor.discord.requests.post')
    def test_partial_report_records_only_successful_batches(self,post):
        post.side_effect=[Mock(status_code=200),RuntimeError('network failure')]
        saved=[]
        with self.assertRaises(RuntimeError):
            send_report('https://example.test',[row(i) for i in range(40)],'general','now',on_sent=lambda jobs:saved.extend(jobs))
        self.assertGreater(len(saved),0)
        self.assertLess(len(saved),40)
    def test_repeated_report_and_previous_alert_do_not_post_again(self):
        state={};j,c,a=row(1);mark(state,'ats',[j])
        with tempfile.TemporaryDirectory() as tmp, patch.object(run,'BASE',Path(tmp)),patch.object(run,'load_state',return_value=state),patch.object(run,'write_state'),patch.dict(run.os.environ,{'DISCORD_WEBHOOK_ATS':'https://example.test'}),patch.object(run,'send_report') as send:
            self.assertEqual(run.report([(j,c,a)],'ats','now'),0)
            send.assert_not_called()
    def test_report_checkpoint_persists_and_retry_filters_sent_jobs(self):
        state={};rows=[row(1),row(2)]
        def send_hook(url,selected,*args,**kwargs):kwargs['on_sent']([r[0] for r in selected])
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'BASE',Path(tmp)),patch.object(run,'load_state',return_value=state),patch.object(run,'write_state') as write,patch.dict(run.os.environ,{'DISCORD_WEBHOOK_ATS':'https://example.test'}),patch.object(run,'send_report',side_effect=send_hook) as send:
            self.assertEqual(run.report(rows,'ats','now'),0)
            self.assertEqual(run.report(rows,'ats','later'),0)
            self.assertEqual(send.call_count,1)
            write.assert_called()

class BotStorage(unittest.TestCase):
    def test_parser_and_restart_persistence(self):
        embed={'title':'IT Support','url':'https://example.com/job/1','description':'**Company:** Employer\n**Location:** Cork\n**Apply:** [Apply](https://example.com/job/1)'}
        jobs=jobs_from_embeds([embed,embed]);self.assertEqual(len(jobs),1)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bot.sqlite3';store=Store(path);store.save_jobs(jobs,'https://discord.com/channels/1/2/3');store.save_companion(3,4,jobs,channel=2)
            store.mark_application(10,jobs[0]['key'],20);store.mark_application(10,jobs[0]['key'],20);store.db.close()
            again=Store(path)
            self.assertEqual(again.application(10,jobs[0]['key']),'20')
            self.assertIsNone(again.application(11,jobs[0]['key']))
            self.assertEqual(again.companion(3),('4',))
            self.assertIn(jobs[0]['key'],again.tracked_jobs(2))
            self.assertNotIn(jobs[0]['key'],again.tracked_jobs(5))
            self.assertEqual(again.job(jobs[0]['key'])['url'],embed['url'])
            self.assertEqual(again.db.execute('SELECT COUNT(*) FROM applications').fetchone()[0],1)
            again.db.close()
    def test_compact_cards_and_unsafe_links(self):
        a={'title':'Support','description':'Employer · Cork\n**Apply:** [Apply](https://example.com/1)'}
        self.assertEqual(jobs_from_embeds([a])[0]['company'],'Employer')
        self.assertEqual(jobs_from_embeds([{'title':'Bad','url':'javascript:alert(1)'}]),[])
