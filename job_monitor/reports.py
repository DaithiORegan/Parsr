"""Complete vacancy snapshots, conservative deduplication and ranked previews."""
import csv
import io
import re
from urllib.parse import urlsplit, parse_qsl, urlencode
from job_monitor.routing import eligible_for_channel, is_cork_kerry

AGGREGATORS = {'jooble', 'remotive', 'rss', 'jobsie', 'irishjobs'}

def normal(value):
    return ' '.join(re.findall(r'\w+', str(value).casefold()))

def canonical_url(value):
    p = urlsplit(value)
    query = [(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in {'ref','source','trackingid'}]
    return (p.netloc.lower(), p.path.rstrip('/'), urlencode(sorted(query))) if p.netloc else None

def deduplicate(rows):
    # Prefer direct listings. Only merge exact normalized employer/title/location
    # or identical application URLs; never fuzzy-match unrelated vacancies.
    result, urls, fingerprints = [], set(), {}
    for row in sorted(rows, key=lambda r: r[0].get('provider') in AGGREGATORS):
        j = row[0]
        url = canonical_url(j.get('url',''))
        fp = tuple(normal(j.get(k,'')) for k in ('company','title','location'))
        known = all(fp) and fp[0] not in {'unknown company', 'unknown', 'unspecified'}
        if (url and url in urls) or (known and fp in fingerprints):
            continue
        if url: urls.add(url)
        if known: fingerprints.setdefault(fp, set()).add(j.get('provider'))
        result.append(row)
    return result

def ranked(rows):
    return sorted(deduplicate(rows), key=lambda r: (-r[2]['score'], not is_cork_kerry(r[0]), r[0]['company'].casefold(), r[0]['title'].casefold()))

def highlights(rows):
    rows = ranked(rows)
    direct = [r for r in rows if r[0].get('provider') not in AGGREGATORS]
    other = [r for r in rows if r[0].get('provider') in AGGREGATORS]
    # Reserve up to four of six preview places for employers; CSV stays complete.
    selected = direct[:4] + other[:max(0,6-min(4,len(direct)))]
    ids = {r[0]['id'] for r in selected}
    selected += [r for r in rows if r[0]['id'] not in ids][:6-len(selected)]
    return sorted(selected, key=lambda r: -r[2]['score'])

def channel_rows(rows, channel):
    return ranked([r for r in rows if eligible_for_channel(channel, r[0], r[2])])

def csv_bytes(rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['Company','Job title','Location','Experience requirement','Fit score','Short description','Application link','Source','Category'])
    for j,c,a in ranked(rows):
        values = [j['company'], j['title'], j['location'], a['experience'], a['score'], a['description'], j['url'], j['provider'], c]
        # Prevent spreadsheet formulas in externally supplied listing text.
        writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return output.getvalue().encode('utf-8-sig')

