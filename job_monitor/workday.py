"""Read public Workday career search data with Ireland country filtering."""
from urllib.parse import urlparse
import json
import re
from pathlib import Path


def workday(session, source):
    from job_monitor.collectors import _clean_job
    from job_monitor.filters import matching_category
    parsed = urlparse(source['url'])
    if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.myworkdayjobs.com'):
        raise ValueError('Workday requires a public myworkdayjobs.com career URL')
    tenant = parsed.hostname.split('.')[0]
    site = parsed.path.strip('/')
    if not site or '/' in site:
        raise ValueError('Workday URL must identify one career site')
    origin = 'https://' + parsed.hostname
    api = f'{origin}/wday/cxs/{tenant}/{site}'

    def page(offset, facets):
        r = session.post(api + '/jobs', json={'appliedFacets': facets, 'limit': 20,
                                             'offset': offset, 'searchText': ''}, timeout=25)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data.get('jobPostings'), list) or 'total' not in data:
            raise ValueError('Workday search schema changed')
        return data

    first = page(0, {})
    def country(nodes, names=('locationcountry',)):
        for node in nodes:
            if node.get('facetParameter', '').replace('_', '').casefold() in names:
                return node
            found = country(node.get('values', []), names)
            if found: return found
        return None
    facet = country(first.get('facets', []))
    if facet:
        ids = [v['id'] for v in facet['values'] if v.get('descriptor', '').casefold() == 'ireland']
    else:
        facet = country(first.get('facets', []), ('locations',))
        if not facet:
            if first['total'] == 0: return []
            raise ValueError('Workday location filter missing')
        irish = re.compile(r'\b(ireland|irl|cork|dublin|galway|limerick|waterford|letterkenny|athlone)\b', re.I)
        ids = [v['id'] for v in facet['values'] if irish.search(v.get('descriptor', ''))]
    if not ids: return []
    facets = {facet['facetParameter']: ids}
    filters = json.loads((Path(__file__).parent.parent / 'config/filters.json').read_text())
    jobs = []
    for offset in range(0, 5000, 20):
        data = page(offset, facets)
        for item in data['jobPostings']:
            path = item.get('externalPath', '')
            if not path.startswith('/job/') or not item.get('title'):
                continue
            raw_id = (item.get('bulletFields') or [path.rsplit('/', 1)[-1]])[0]
            location = item.get('locationsText') or 'Ireland'
            job = _clean_job('workday', source, str(raw_id), item['title'],
                             [location], f'{origin}/en-US/{site}{path}',
                             posted=item.get('postedOn') or '')
            # Detail data resolves "multiple locations" and supplies actual requirements.
            # Only Ireland country-filtered postings are returned from this endpoint.
            candidate = dict(job, location=location + '; Ireland')
            if matching_category(candidate, filters):
                r = session.get(api + path, timeout=25)
                r.raise_for_status()
                info = r.json().get('jobPostingInfo')
                if not isinstance(info, dict):
                    raise ValueError('Workday job detail schema changed')
                locations = [info.get('location') or location]
                locations.extend(info.get('additionalLocations') or [])
                job['location'] = '; '.join(str(v) for v in locations if v) + '; Ireland'
                job['description'] = str(info.get('jobDescription') or '')[:6000]
                job['posted'] = info.get('startDate') or job['posted']
            else:
                job['location'] += '; Ireland'
            jobs.append(job)
        if offset + len(data['jobPostings']) >= int(data['total']):
            return jobs
        if not data['jobPostings']:
            raise ValueError('Workday pagination ended before total')
    raise ValueError('Workday Ireland results exceeded pagination budget')
