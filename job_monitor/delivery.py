"""Persistent per-channel identities shared by reports, alerts and backfill."""
import hashlib
import json
from job_monitor.reports import canonical_url, normal
from job_monitor.routing import eligible_for_channel

def keys(job):
    result = set()
    url = canonical_url(job.get('url', ''))
    if url:
        result.add('url:'+hashlib.sha256(json.dumps(url).encode()).hexdigest())
    fp = tuple(normal(job.get(k, '')) for k in ('company','title','location'))
    if all(fp) and fp[0] not in {'unknown','unknown company','unspecified'}:
        result.add('job:'+hashlib.sha256(json.dumps(fp).encode()).hexdigest())
    if not result and job.get('id'):
        result.add('id:'+str(job['id']))
    return result

def delivered(state, channel, job):
    return bool(keys(job) & set(state.get('delivered_by_channel', {}).get(channel, [])))

def mark(state, channel, jobs):
    history = state.setdefault('delivered_by_channel', {})
    known = set(history.get(channel, []))
    for job in jobs:
        known.update(keys(job))
    history[channel] = sorted(known)

def migrate(state):
    if state.get('delivery_history_version') == 1:
        return state
    # Previous versions sent full snapshots without recording report deliveries.
    # Treat the pre-upgrade index as historical so the upgrade does not replay it.
    for jid, record in state.get('job_index', {}).items():
        job = dict(record, id=jid)
        for channel in ('general','local','ats'):
            if eligible_for_channel(channel, job, {'score':record.get('fit_score',0),'experience':record.get('experience','')}):
                mark(state, channel, [job])
    state['delivery_history_version'] = 1
    return state
