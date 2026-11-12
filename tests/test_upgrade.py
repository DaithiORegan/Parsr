"""Offline regression tests for upgrade behaviour and quiet feed onboarding."""
import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
import run


class UpgradeTests(TestCase):
    def _job(self, company, number, provider='greenhouse', slug='example'):
        return {'id': f'{provider}:{slug}:{number}', 'title':'IT Support Engineer',
                'company':company, 'location':'Cork, Ireland',
                'url':'https://example.org/job/'+str(number),
                'provider':provider, 'salary':'', 'posted':''}

    def test_unseen_excludes_legacy_jobs_and_preserves_first_index_time(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json'
            path.write_text(json.dumps({'initialized':False,'seen':{},'baselined_sources':[],
                'job_index':{'greenhouse:example:1':{'title':'Legacy role'},
                             'greenhouse:example:2':{'first_indexed_at':'2026-11-12T22:30:00+00:00'}}}))
            rows=[self._job('Legacy',1),self._job('Tracked',2),self._job('New Employer',3)]
            source=[{'provider':'greenhouse','slug':'example','company':'Example'}]
            with patch.object(run,'STATE_PATH',path),patch.object(run,'load_sources',return_value=source), \
                 patch.object(run,'collect',return_value=(rows,[],{'greenhouse:example'})), \
                 patch.object(run,'session_with_retries',return_value=None),patch.dict(run.os.environ,{},clear=True):
                with patch.object(run,'utc_now',return_value='2026-11-12T23:00:00+00:00'):
                    self.assertEqual(run.scan(),0)
                indexed=json.loads(path.read_text())['job_index']
                self.assertNotIn('first_indexed_at',indexed['greenhouse:example:1'])
                self.assertEqual(indexed['greenhouse:example:2']['first_indexed_at'],'2026-11-12T22:30:00+00:00')
                self.assertEqual(indexed['greenhouse:example:3']['first_indexed_at'],'2026-11-12T23:00:00+00:00')
                with patch.object(run,'utc_now',return_value='2026-11-13T11:00:00+00:00'):
                    self.assertEqual(run.scan(),0)
                indexed=json.loads(path.read_text())['job_index']
                self.assertNotIn('first_indexed_at',indexed['greenhouse:example:1'])
                self.assertEqual(indexed['greenhouse:example:3']['first_indexed_at'],'2026-11-12T23:00:00+00:00')

    def test_migrates_legacy_state_and_silently_baselines_new_feeds(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'state.json'
            p.write_text(json.dumps({'initialized': True,'seen':{'greenhouse:existing:1':'2026-11-10T00:00:00+00:00'},
                                     'last_scan_utc':'2026-11-10T00:00:00+00:00'}))
            a = self._job('Existing', 1, slug='existing')
            b = self._job('Fresh Board', 2, slug='fresh')
            fake_sources = [{'provider':'greenhouse','slug':'existing','company':'Existing'},
                            {'provider':'greenhouse','slug':'fresh','company':'Fresh Board'}]
            with patch.object(run, 'STATE_PATH', p), patch.object(run, 'load_sources', return_value=fake_sources), \
                 patch.object(run, 'collect', return_value=([a,b],[],{'greenhouse:existing','greenhouse:fresh'})), \
                 patch.object(run, 'session_with_retries', return_value=None), \
                 patch.object(run, 'send_job') as send, patch.dict(run.os.environ, {'DISCORD_WEBHOOK_URL':'https://discord.example/webhook'}):
                self.assertEqual(run.scan(), 0)
                send.assert_not_called()
            after=json.loads(p.read_text())
            self.assertIn('greenhouse:fresh:2', after['seen'])
            self.assertIn('greenhouse:fresh', after['baselined_sources'])
            # Subsequent genuinely new posting on the same board must send an alert.
            c = self._job('Fresh Board', 3, slug='fresh')
            c['title'] = 'Desktop Support Engineer'  # A genuinely different role, not a duplicate posting.
            with patch.object(run, 'STATE_PATH', p), patch.object(run, 'load_sources', return_value=fake_sources), \
                 patch.object(run, 'collect', return_value=([a,b,c],[],{'greenhouse:existing','greenhouse:fresh'})), \
                 patch.object(run, 'session_with_retries', return_value=None), \
                 patch.object(run, 'send_job') as send, patch.dict(run.os.environ, {'DISCORD_WEBHOOK_URL':'https://discord.example/webhook'}):
                self.assertEqual(run.scan(),0)
                send.assert_called_once()
            self.assertIn('greenhouse:fresh:3',json.loads(p.read_text())['seen'])

    def test_preview_does_not_modify_history(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'state.json'
            old='{"initialized": true, "seen": {"greenhouse:existing:1":"old"}}'
            p.write_text(old)
            with patch.object(run, 'STATE_PATH', p), patch.object(run, 'load_sources', return_value=[{'provider':'greenhouse','slug':'fresh','company':'Fresh'}]), \
                 patch.object(run, 'collect', return_value=([self._job('Fresh',2,slug='fresh')],[],{'greenhouse:fresh'})), \
                 patch.object(run, 'session_with_retries', return_value=None), patch.object(run, 'send_job') as send:
                self.assertEqual(run.scan(dry_run=True), 0)
                send.assert_not_called()
            self.assertEqual(p.read_text(), old)

    def test_failed_new_source_not_baselined(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'state.json'
            p.write_text(json.dumps({'initialized':True,'seen':{'greenhouse:existing:1':'old'},'baselined_sources':['greenhouse:existing']}))
            with patch.object(run,'STATE_PATH',p), patch.object(run,'load_sources', return_value=[{'provider':'greenhouse','slug':'fresh','company':'Fresh'}]), \
                patch.object(run,'collect',return_value=([self._job('Existing',1,slug='existing')],['Fresh: timed out'],{'greenhouse:existing'})), \
                patch.object(run,'session_with_retries',return_value=None):
                self.assertEqual(run.scan(),0)
            self.assertNotIn('greenhouse:fresh',json.loads(p.read_text())['baselined_sources'])
