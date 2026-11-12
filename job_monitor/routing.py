"""Explicit location routing and independently configurable Discord destinations."""
from __future__ import annotations
import re

CORK = re.compile(r"\b(cork|county cork|co\.? cork|mallow|midleton|cobh|fermoy|clonakilty|bantry|skibbereen|little island|ballincollig|carrigaline)\b", re.I)

def is_cork(job: dict) -> bool:
    # Only structured location field, not mentions in job description or company name.
    return bool(CORK.search(job.get('location','')))

def eligible_for_channel(channel: str, job: dict, assessment: dict) -> bool:
    if channel == 'general': return True
    if channel == 'local': return is_cork(job)
    if channel == 'ats':
        years = assessment.get('experience_years')
        if years is None:
            match = re.search(r'(\d+)\+? years', assessment.get('experience', ''))
            years = int(match.group(1)) if match else None
        return (is_cork(job) and assessment.get('score', 0) >= 78
                and assessment.get('level') != 'Senior / leadership'
                and (years is None or years <= 2))
    return False

def channel_threshold(channel: str, profile: dict) -> int:
    if channel == 'ats': return 78
    if channel == 'local': return 0
    return 0

def target_webhooks(environ) -> dict:
    channels = {
        'general':environ.get('DISCORD_WEBHOOK_URL','').strip(),
        'local':environ.get('DISCORD_WEBHOOK_LOCAL','').strip(),
        'ats':environ.get('DISCORD_WEBHOOK_ATS','').strip(),
    }
    configured = [url for url in channels.values() if url]
    if len(set(configured)) != len(configured):
        raise ValueError('Each Discord channel must use a distinct webhook URL')
    return channels


# Compatibility for local ranking callers; local feeds now mean Cork only.
is_cork_kerry = is_cork

