"""Allow one successful scheduled scan per Dublin morning/evening slot.

GitHub creates two attempts per slot. Successful workflow history is the durable
marker, avoiding changes to job-state merging and avoiding duplicate reports.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DUBLIN = ZoneInfo('Europe/Dublin')

def slot_start(created):
    local = created.astimezone(DUBLIN)
    if local.hour >= 22:
        return local.replace(hour=22, minute=0, second=0, microsecond=0)
    if local.hour >= 10:
        return local.replace(hour=10, minute=0, second=0, microsecond=0)
    return (local-timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)

def already_succeeded(runs, current_id, created):
    start = slot_start(created)
    # Replace the local clock hour rather than adding UTC hours across DST.
    end = start.replace(hour=22) if start.hour == 10 else (start+timedelta(days=1)).replace(hour=10)
    for run in runs:
        if str(run.get('id')) == str(current_id):
            continue
        if run.get('event') != 'schedule' or run.get('conclusion') != 'success':
            continue
        timestamp = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        if start <= timestamp.astimezone(DUBLIN) < end:
            return True
    return False

def main():
    needed = True
    if os.environ.get('GITHUB_EVENT_NAME') == 'schedule':
        repo = os.environ['GITHUB_REPOSITORY']
        current_id = os.environ['GITHUB_RUN_ID']
        token = os.environ['GITHUB_TOKEN']
        def get(path):
            request = Request('https://api.github.com/repos/'+repo+path,
                              headers={'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                                       'User-Agent':'IrishITJobMonitor-schedule'})
            with urlopen(request, timeout=25) as response:
                return json.load(response)
        current = get('/actions/runs/'+current_id)
        created = datetime.fromisoformat(current['created_at'].replace('Z', '+00:00'))
        query = urlencode({'event':'schedule','status':'success','per_page':100,
                           'created':'>='+slot_start(created).astimezone(timezone.utc).isoformat()})
        workflow = os.environ.get('SCHEDULE_WORKFLOW', 'monitor.yml')
        history = get('/actions/workflows/'+workflow+'/runs?'+query)
        needed = not already_succeeded(history['workflow_runs'], current_id, created)
        print('Scheduled slot:', slot_start(created).isoformat())
    print('Scan required.' if needed else 'This slot already has a successful scan; skipping backup.')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('run_scan='+str(needed).lower()+'\n')

if __name__ == '__main__':
    main()
