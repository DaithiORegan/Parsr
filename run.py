"""Irish IT Job Monitor v2: public ATS feeds -> filtering -> Discord.

Important upgrade guarantee: new feeds begin with a quiet baseline so expanding
coverage doesn't produce alerts for hundreds of already-advertised vacancies.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from job_monitor.collectors import collect, load_sources, session_with_retries, source_availability
from job_monitor.discord import send_job, send_test, send_report
from job_monitor.filters import matching_category
from job_monitor.evaluate import evaluate
from job_monitor.routing import target_webhooks, eligible_for_channel, channel_threshold

from job_monitor.reports import deduplicate, channel_rows, csv_bytes
from job_monitor.delivery import delivered as is_delivered, mark, migrate

BASE = Path(__file__).resolve().parent
STATE_PATH = BASE / 'data' / 'state.json'


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def source_key(job_id: str) -> str:
    """Provider:slug remains stable across releases; posting IDs may contain colons."""
    return ':'.join(job_id.split(':', 2)[:2])


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {'initialized': False, 'seen': {}, 'baselined_sources': [], 'last_scan_utc': None}
    state = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    if not isinstance(state.get('seen'), dict):
        raise ValueError('data/state.json must contain a seen object')
    if 'baselined_sources' not in state:
        # Migrate v1 state. All previously recorded sources are already established.
        state['baselined_sources'] = sorted({source_key(k) for k in state['seen']})
    if not isinstance(state['baselined_sources'], list):
        raise ValueError('baselined_sources must be a list')
    return migrate(state)


def write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(STATE_PATH)


def report(rows, channel, snapshot, dry_run=False, partial=False, cached=False):
    channels = target_webhooks(os.environ)
    names = list(channels) if channel == 'all' else [channel]
    failed = False
    delivery_state = load_state()
    for name in names:
        selected = channel_rows(rows, name)
        path = BASE / 'data' / f'vacancies-{name}.csv'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(csv_bytes(selected))
        print(f'{name}: {len(selected)} vacancies exported to {path.name}; snapshot {snapshot}')
        if dry_run: continue
        selected = [row for row in selected if not is_delivered(delivery_state, name, row[0])]
        if not selected:
            print(f'{name}: no unsent jobs; no Discord post')
            continue
        if not channels[name]:
            print(f'{name}: webhook missing; report not sent')
            failed = True
            continue
        try:
            def checkpoint(jobs):
                mark(delivery_state, name, jobs)
                write_state(delivery_state)
            send_report(channels[name], selected, name, snapshot, partial, cached, on_sent=checkpoint)
        except Exception as exc:
            print(f'{name}: report failed ({type(exc).__name__}); webhook withheld')
            failed = True
    return int(failed)


def saved_report(channel, dry_run=False):
    state = load_state()
    rows = []
    profile = json.loads((BASE / 'config' / 'candidate_profile.json').read_text())
    for jid, record in state.get('job_index', {}).items():
        job = dict(record, id=jid)
        assessment = evaluate(job, job['category'], profile)
        assessment.update(score=record.get('fit_score', assessment['score']),
                          experience=record.get('experience', assessment['experience']),
                          description=record.get('description', assessment['description']))
        assessment['rating'] = 'Strong' if assessment['score'] >= 78 else 'Possible' if assessment['score'] >= 58 else 'Low'
        rows.append((job, job['category'], assessment))
    if not rows:
        print('No saved vacancies; run a scan first.')
        return 2
    return report(rows, channel, state.get('last_scan_utc') or 'unknown', dry_run, cached=True)


def scan(dry_run: bool = False, list_only: bool = False, backfill: bool = False, limit: int | None = None, channel: str = "general", full_report: bool = False, with_report: bool = False) -> int:
    configured = load_sources(BASE / 'config' / 'sources.csv')
    sources, locked = [], []
    for src in configured:
        ready, reason = source_availability(src)
        (sources if ready else locked).append(src if ready else (src, reason))
    if list_only:
        print(f'Configured sources: {len(configured)} | accessible without extra keys: {len(sources)} | locked: {len(locked)}')
        for src in sources:
            print(f"  [CONFIGURED] {src['provider']:16} {src['slug']:22} {src['company']}")
        for src, reason in locked:
            print(f"  [LOCKED] {src['company']} — {reason}")
        return 0
    if not sources:
        print('No enabled sources in config/sources.csv')
        return 2
    filters = json.loads((BASE / 'config' / 'filters.json').read_text(encoding='utf-8'))
    profile = json.loads((BASE / 'config' / 'candidate_profile.json').read_text(encoding='utf-8'))
    state = load_state()
    old_seen = state['seen']
    backfill_sent = set(state.get('backfill_sent', []))
    backfill_by_channel = state.setdefault('backfill_by_channel', {})
    alert_sent_by_channel = state.setdefault('alert_sent_by_channel', {})
    prev_baselined = set(state['baselined_sources'])
    webhook = os.getenv('DISCORD_WEBHOOK_URL', '').strip()
    for src, reason in locked:
        print(f"[LOCKED] {src['company']}: {reason}")
    print(f'Checking {len(sources)} accessible feeds... {utc_now()}')
    jobs, errors, successes = collect(session_with_retries(), sources)
    source_health = {
        'attempted_at': utc_now(), 'successful_sources': len(successes),
        'failed_sources': [{'provider':src['provider'],'company':src['company']} for src in sources
                           if src.get('key', source_key(src['provider']+':'+src['slug'])) not in successes],
        'locked_sources': [{'provider':src['provider'],'company':src['company']} for src, reason in locked],
        'partial_sources': [{'provider':src['provider'],'company':src['company'],**src['query_status']} for src in sources
                            if src.get('query_status',{}).get('failed_or_truncated')],
    }
    health_changed = False
    if not (dry_run or backfill or full_report):
        health_changed = state.get('scan_health') != source_health
        state['scan_health'] = source_health
    if not successes:
        if health_changed: write_state(state)
        print('Every source failed; preserving history and stopping.')
        return 1
    unique = {j['id']: j for j in jobs}
    matched = []
    for j in unique.values():
        category = matching_category(j, filters)
        if category:
            matched.append((j, category, evaluate(j,category,profile)))
    matched = deduplicate(matched)
    if full_report:
        return report(matched, channel, utc_now(), dry_run, partial=bool(errors))
    # Lightweight index for later application tracking; no application is submitted.
    job_index = state.setdefault('job_index', {})
    index_changed = health_changed
    for j, category, assessment in matched:
        record = {'company':j['company'],'title':j['title'],'location':j['location'],
                  'url':j['url'],'category':category,'fit_score':assessment['score'],
                  'experience':assessment['experience'],'posted':j.get('posted',''),
                  'provider':j['provider'],'description':assessment['description'],
                  'full_description':j.get('description',''), 'salary':j.get('salary',''), 'last_seen':utc_now()}
        if job_index.get(j['id']) != record:
            job_index[j['id']] = record
            index_changed = True
    new_feed_keys = successes - prev_baselined
    print(f'Published jobs: {len(unique)} | Irish IT matches: {len(matched)} | Configured sources succeeded: {len(successes)}')
    if new_feed_keys:
        print(f'New sources to baseline quietly: {len(new_feed_keys)}')
    if backfill:
        minimum = int(profile.get('backfill_min_score',58))
        max_n = max(1, min(30, limit or int(profile.get('backfill_max_per_run',15))))
        if channel not in ('general','local','ats'):
            print('Unknown channel choice'); return 2
        channels = target_webhooks(os.environ)
        webhook = channels.get(channel, '')
        if channel == 'ats': minimum = 78
        elif channel == 'local': minimum = int(profile.get('local_min_score', 0))
        prior = backfill_sent if channel == 'general' else set(backfill_by_channel.get(channel, []))
        eligible = [(j,c,a) for j,c,a in matched if a['score']>=minimum and eligible_for_channel(channel,j,a) and j['id'] not in prior and not is_delivered(state, channel, j)]
        eligible.sort(key=lambda item:(item[2]['score'], item[1]=='IT Support / Technical'),reverse=True)
        selected=[]
        fingerprints=set()
        for j,c,a in eligible:
            fingerprint=(j['company'].casefold().strip(), j['title'].casefold().strip(), j['location'].casefold().strip())
            if fingerprint in fingerprints: continue
            fingerprints.add(fingerprint)
            selected.append((j,c,a))
            if len(selected)>=max_n: break
        print(f'Filtered {channel} backfill: {len(eligible)} eligible | {len(selected)} selected | threshold {minimum}/100')
        if dry_run:
            print('BACKFILL PREVIEW: no state changes or Discord messages')
            for j,c,a in selected:
                print(f"[{a['score']}/100 | {a['level']}] {j['title']} | {j['company']} | {j['location']} | {j['url']}")
            return 0
        if not webhook:
            print('Discord webhook not configured; backfill not sent.')
            return 2
        successful = 0
        failed = 0
        for j,c,a in selected:
            try:
                send_job(webhook,j,c,a,is_backfill=True,compact=channel == 'ats')
            except Exception as exc:
                print(f'[BACKFILL ERROR] {j["title"]}: {type(exc).__name__}; webhook URL withheld')
                failed += 1
                continue
            mark(state, channel, [j])
            if channel == 'general':
                backfill_sent.add(j['id'])
                state['backfill_sent'] = sorted(backfill_sent)
            else:
                prior.add(j['id'])
                backfill_by_channel[channel] = sorted(prior)
            write_state(state)  # Recoverable if Discord stops halfway through the batch
            successful += 1
            print(f'[SENT] {a["score"]}/100 {j["title"]} — {j["company"]}')
        print(f'Backfill: {successful} delivered, {failed} failed. Remaining candidates can be sent with another backfill run.')
        return 1 if failed else 0
    if dry_run:
        print('PREVIEW: no Discord messages, no state changes')
        for j,c,a in sorted((item for item in matched if item[0]['id'] not in old_seen),key=lambda x:x[2]['score'],reverse=True)[:60]:
            marker = 'BASELINE' if source_key(j['id']) in new_feed_keys else 'NEW'
            print(f'[{marker} {a["score"]}/100 {a["level"]}] {j["title"]} | {j["company"]} | {j["location"]} | {j["url"]}')
        print(f'No state changes. Errors: {len(errors)}')
        return 0
    now=utc_now()
    changed=index_changed
    quiet_initial = not state.get('initialized',False)
    if quiet_initial:
        for jid in unique:
            if jid not in old_seen:
                old_seen[jid]=now; changed=True
        state['initialized']=True;changed=True
        print('Initial state recorded silently.')
    else:
        delivered=failed=excluded=0
        channels = target_webhooks(os.environ)
        lookup={j['id']:(j,c,a) for j,c,a in matched}
        # Each channel has its own send history, so partially completed fan-out
        # can retry without reposting to channels that already succeeded.
        for j in unique.values():
            jid=j['id']
            if jid in old_seen: continue
            if source_key(jid) in new_feed_keys:
                old_seen[jid]=now;changed=True;continue
            match=lookup.get(jid)
            if match:
                _, category, assessment = match
                destinations = [name for name in channels if channels[name] and eligible_for_channel(name, j, assessment)
                                and assessment['score'] >= channel_threshold(name,profile)]
                if not destinations: excluded+=1
                pending=[]
                for name in destinations:
                    already=set(alert_sent_by_channel.get(name, []))
                    if jid in already or is_delivered(state, name, j): continue
                    url=channels[name]
                    if not url:
                        print(f'[PENDING] {j["title"]}: missing {name} Discord webhook')
                        pending.append(name); failed+=1;continue
                    try:
                        send_job(url,j,category,assessment,compact=name == 'ats')
                        mark(state, name, [j])
                        already.add(jid)
                        alert_sent_by_channel[name]=sorted(already)
                        write_state(state)
                        delivered+=1
                        print(f'[ALERT:{name}] {assessment["score"]}/100 {j["title"]} at {j["company"]}')
                    except Exception as exc:
                        print(f'[ALERT FAILED:{name}] {j["title"]}: {type(exc).__name__}; webhook withheld')
                        pending.append(name);failed+=1
                if pending: continue
            old_seen[jid]=now;changed=True
        print(f'Completed: {delivered} channel alerts, {excluded} low-fit excluded, {failed} pending, {len(errors)} source errors.')
    if new_feed_keys:
        state['baselined_sources']=sorted(prev_baselined|new_feed_keys)
        changed=True
    if changed:
        state['last_scan_utc']=now
        write_state(state)
    if errors: print('Warning: some sources failed, but successful feeds were still processed.')
    report_failed = report(matched, 'all', now, partial=bool(errors)) if with_report else 0
    return 1 if report_failed or (not quiet_initial and failed) else 0


def main() -> int:
    load_dotenv(BASE / '.env')
    ap = argparse.ArgumentParser(description='Monitor published Irish IT jobs')
    ap.add_argument('--dry-run', action='store_true', help='Preview without changing state')
    ap.add_argument('--test-discord', action='store_true', help='Send a test Discord notification')
    ap.add_argument('--list-sources', action='store_true', help='Show configured sources')
    ap.add_argument('--backfill', action='store_true', help='Send a limited batch of existing relevant jobs (manual only)')
    ap.add_argument('--channel', choices=['general','local','ats','all'], default='general', help='Channel used by backfill and Discord test')
    ap.add_argument('--with-report', action='store_true', help='Send unsent matching jobs after normal alerts')
    ap.add_argument('--report', action='store_true', help='Scan and send unsent matching job cards to Discord')
    ap.add_argument('--saved-report', action='store_true', help='Export saved results without a new scan; availability unverified')
    ap.add_argument('--limit', type=int, default=None, help='Maximum jobs per backfill run, capped at 30')
    args = ap.parse_args()
    if args.saved_report:
        return saved_report(args.channel, args.dry_run)
    if args.channel == 'all' and not args.report:
        ap.error('--channel all requires --report or --saved-report')
    if args.report and args.backfill:
        ap.error('--report and --backfill cannot be combined')
    if args.test_discord:
        webhook = target_webhooks(os.environ).get(args.channel, '')
        if not webhook:
            print('DISCORD_WEBHOOK_URL is missing from .env / GitHub secret')
            return 2
        try:
            send_test(webhook,compact=args.channel == 'ats')
            print('Discord test notification sent.')
            return 0
        except Exception as exc:
            print(f'Discord test failed: {type(exc).__name__}. Webhook withheld.')
            return 1
    return scan(args.dry_run, args.list_sources, args.backfill, args.limit, args.channel, args.report, args.with_report)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f'Configuration problem: {exc}')
        sys.exit(2)


