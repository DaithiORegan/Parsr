import unittest
from datetime import datetime, timezone
from schedule_gate import slot_start, already_succeeded

class Schedule(unittest.TestCase):
    def run_record(self, id=1, at='2026-11-12T10:17:00Z', event='schedule', result='success'):
        return dict(id=id,created_at=at,event=event,conclusion=result)
    def test_backup_skips_successful_primary(self):
        self.assertTrue(already_succeeded([self.run_record()],2,datetime(2026,11,12,10,47,tzinfo=timezone.utc)))
    def test_failure_manual_and_other_slot_do_not_block(self):
        now=datetime(2026,11,12,22,47,tzinfo=timezone.utc)
        rows=[self.run_record(),self.run_record(3,'2026-11-12T22:17:00Z',result='failure'),self.run_record(4,'2026-11-12T22:20:00Z',event='workflow_dispatch')]
        self.assertFalse(already_succeeded(rows,2,now))
    def test_current_run_does_not_block_itself(self):
        self.assertFalse(already_succeeded([self.run_record()],1,datetime(2026,11,12,10,47,tzinfo=timezone.utc)))
    def test_summer_uses_irish_local_time(self):
        now=datetime(2027,7,12,9,47,tzinfo=timezone.utc)
        self.assertEqual(slot_start(now).hour,10)
        self.assertTrue(already_succeeded([self.run_record(at='2027-07-12T09:17:00Z')],2,now))
    def test_previous_evening_and_day_do_not_block(self):
        now=datetime(2026,11,12,10,47,tzinfo=timezone.utc)
        self.assertFalse(already_succeeded([self.run_record(at='2026-11-11T22:17:00Z')],2,now))
