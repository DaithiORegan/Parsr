"""Discord job cards, batched within Discord limits; never upload attachments."""
from __future__ import annotations
from datetime import datetime, timezone
import time
from urllib.parse import urlparse
import requests


def job_embed(job, category, assessment=None, is_backfill=False, compact=False):
    a = assessment or {}
    url = job.get('url', '')
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or len(url) > 2048:
        raise ValueError('Job has no valid application URL')
    company = str(job.get('company', 'Not specified'))[:150]
    location = str(job.get('location', 'Not specified'))[:150]
    fit = f"{a.get('rating', 'Not specified')} ({a.get('score', 0)}/100) — heuristic, not an ATS score"
    if compact:
        lines = [f"{company} · {location}", f"**CV fit estimate:** {fit}",
                 f"**Experience requirement:** {a.get('experience', 'Not stated in available listing data')[:180]}"]
    else:
        lines = [f"**Company:** {company}", f"**Location:** {location}",
                 f"**Category:** {category[:150]}",
                 f"**Experience level:** {a.get('level', 'Not specified')}",
                 f"**Experience requirement:** {a.get('experience', 'Not stated in available listing data')[:180]}",
                 f"**CV fit estimate:** {fit}",
                 f"**Summary:** {a.get('description') or job.get('description') or 'Open the original advert for duties and requirements.'}"[:700]]
        if a.get('matched_skills'):
            lines.append('**Relevant skills:** ' + ', '.join(a['matched_skills'])[:250])
        if job.get('salary'):
            lines.append(f"**Salary:** {str(job['salary'])[:150]}")
    lines.extend([f"**Source:** {str(job.get('provider', 'Not specified')).title()[:100]}",
                  f"**Apply:** [Apply for this job]({url})"])
    return {'title': str(job['title'])[:256], 'url': url, 'description': '\n'.join(lines),
            'color': 5763719 if is_backfill else 3066993,
            'footer': {'text': ('Existing vacancy shortlist' if is_backfill else 'Job vacancy') +
                       ' · Verify requirements before applying'},
            'timestamp': datetime.now(timezone.utc).isoformat()}


def post_payload(webhook_url, payload):
    for attempt in range(4):
        response = requests.post(webhook_url, json=payload, timeout=25)
        if response.status_code == 429 and attempt < 3:
            try:
                delay = float(response.json().get('retry_after', 2))
            except (ValueError, TypeError, AttributeError):
                delay = 2
            time.sleep(max(.5, delay))
            continue
        response.raise_for_status()
        return


def send_job(webhook_url, job, category, assessment=None, is_backfill=False, compact=False):
    post_payload(webhook_url, {'username': 'Irish IT Job Monitor', 'allowed_mentions': {'parse': []},
                              'embeds': [job_embed(job, category, assessment, is_backfill, compact)]})


def send_test(webhook_url, compact=False):
    example = {'title': 'Test: IT Support Engineer', 'company': 'Example Company (test only)',
               'location': 'Cork, Ireland', 'url': 'https://example.com', 'provider': 'test'}
    send_job(webhook_url, example, 'IT Support / Technical',
             {'score': 87, 'rating': 'Strong', 'level': 'Junior / graduate',
              'experience': 'Not stated in available listing data',
              'description': 'Test notification to verify the enhanced format.',
              'matched_skills': ['Windows', 'Active Directory']}, compact=compact)


def embed_size(embed):
    return len(embed['title']) + len(embed['description']) + len(embed['footer']['text'])


def send_report(webhook_url, rows, channel, snapshot, partial=False, cached=False, on_sent=None):
    """Send every eligible vacancy as cards, without a six-job cap or files."""
    from job_monitor.reports import channel_rows
    rows = channel_rows(rows, channel)
    labels = {'general': 'All jobs', 'local': 'All Cork jobs', 'ats': 'Apply now — strong CV matches in Cork'}
    lines = [f"**{labels[channel]}: {len(rows)} matching vacancies**", f"Snapshot: {snapshot}",
             'Saved results; availability has not been rechecked.' if cached else 'Vacancies returned by the latest scan.']
    if partial:
        lines.append('Some sources failed; this report is incomplete.')
    payload = {'username': 'Irish IT Job Monitor', 'content': '\n'.join(lines),
               'allowed_mentions': {'parse': []}, 'embeds': []}
    size = 0
    batch = []
    for job, category, assessment in rows:
        embed = job_embed(job, category, assessment, compact=channel == 'ats')
        n = embed_size(embed)
        if payload['embeds'] and (len(payload['embeds']) == 10 or size + n > 6000):
            post_payload(webhook_url, payload)
            if on_sent: on_sent(batch)
            batch = []
            payload = {'username': 'Irish IT Job Monitor', 'allowed_mentions': {'parse': []}, 'embeds': []}
            size = 0
        payload['embeds'].append(embed)
        batch.append(job)
        size += n
    if payload['embeds'] or not rows:
        post_payload(webhook_url, payload)
        if on_sent: on_sent(batch)
